"""DraftingCoordinatorAgent StateGraph (ADR-0013 D1 + ADR-0014 fan-out).

Checkpointed by the SAME MongoDBSaver singleton as the section/Part drafters
— the load-bearing decision (ADR-0013 D1) that lets child interrupts propagate
to a resumable parent state. Coordinator thread_id =
``{solicitation_id}:batch:{request_id}``.

Topology::

    START → plan ─┬─ Send(draft_part_I) ───┐
                  ├─ Send(draft_part_IV) ──┤  (parallel superstep)
                  ├─ resolve_part_ii ──────┤
                  ├─ pass_through_part_iii ─┤
                  └─ generate_boilerplate ─┴→ aggregate ─→ critic → END
                       (D-G,K — spec §2)            └→ END (interrupted)
"""
from __future__ import annotations

from functools import lru_cache

from app.agents.checkpointer import build_mongodb_saver
from app.agents.coordinator.nodes import (
    _aggregate,
    _critic,
    _draft_part_i,
    _draft_part_iv,
    _fan_out_per_part,
    _generate_boilerplate,
    _pass_through_part_iii,
    _plan,
    _resolve_part_ii,
    _route_after_aggregate,
)


@lru_cache(maxsize=1)
def build_coordinator_graph():
    from langgraph.graph import END, START, StateGraph  # noqa: PLC0415

    from app.agents.coordinator.nodes import CoordinatorState  # noqa: PLC0415

    g = StateGraph(CoordinatorState)
    g.add_node("plan", _plan)
    g.add_node("draft_part_I", _draft_part_i)
    g.add_node("draft_part_IV", _draft_part_iv)
    g.add_node("resolve_part_ii", _resolve_part_ii)
    g.add_node("pass_through_part_iii", _pass_through_part_iii)
    g.add_node("generate_boilerplate", _generate_boilerplate)
    g.add_node("aggregate", _aggregate)
    g.add_node("critic", _critic)

    g.add_edge(START, "plan")
    # Dynamic per-Part fan-out (Send); falls through to aggregate when there
    # is nothing to draft.
    g.add_conditional_edges(
        "plan", _fan_out_per_part, ["draft_part_I", "draft_part_IV", "aggregate"]
    )
    # Programmatic + boilerplate Parts run in the same parallel superstep as
    # the Sends (none depend on the agent drafters).
    g.add_edge("plan", "resolve_part_ii")
    g.add_edge("plan", "pass_through_part_iii")
    g.add_edge("plan", "generate_boilerplate")

    g.add_edge("draft_part_I", "aggregate")
    g.add_edge("draft_part_IV", "aggregate")
    g.add_edge("resolve_part_ii", "aggregate")
    g.add_edge("pass_through_part_iii", "aggregate")
    g.add_edge("generate_boilerplate", "aggregate")

    g.add_conditional_edges(
        "aggregate", _route_after_aggregate, {"critic": "critic", END: END}
    )
    g.add_edge("critic", END)

    # ADR-0013 D1 — shares the ADR-0012 D4 MongoDBSaver singleton.
    return g.compile(checkpointer=build_mongodb_saver(), name="batch_coordinator_run")
