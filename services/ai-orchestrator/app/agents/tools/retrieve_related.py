"""``retrieve_related_solicitations`` — programmatic, opportunistic (design ref §8.2).

Null-arg short-circuit returns an empty result with ZERO Mongo cost (~50ms/run
saved). Mongo failure is non-fatal: the tool returns an empty list and the
agent continues (audit flags ``related_unavailable``).
"""
from __future__ import annotations

import logging
from datetime import date

from langchain_core.runnables import RunnableConfig
from langchain.tools import tool

from app import config as app_config
from app.agents.schemas import RelatedSolicitations, SolicitationSummary

log = logging.getLogger("ai-orchestrator.tools.retrieve_related")

_EPOCH = date(1970, 1, 1)


def _query_related(
    tenant_id: str, naics: str | None, set_aside: str | None, k: int
) -> list[dict]:
    """Mongo lookup on the chunks collection, doc_class=internal_solicitation.

    Separate function so tests monkeypatch it without a Mongo round-trip.
    """
    from pymongo import MongoClient  # noqa: PLC0415 — lazy

    fltr: dict = {"tenant_id": tenant_id, "doc_class": "internal_solicitation"}
    if naics:
        fltr["naics"] = naics
    if set_aside:
        fltr["set_aside"] = set_aside
    client = MongoClient(app_config.MONGO_URI, serverSelectionTimeoutMS=1000)
    coll = client[app_config.MONGO_DB][app_config.CHUNKS_COLLECTION]
    return list(coll.find(fltr).limit(k))


@tool
def retrieve_related_solicitations(
    naics: str | None = None,
    set_aside: str | None = None,
    k: int = 5,
    *,
    config: RunnableConfig,
) -> RelatedSolicitations:
    """Retrieve up to `k` related prior solicitations within the caller's tenant.

    Call this only when the run's naics or set_aside is set; skip otherwise.
    Returns an empty result when neither filter is given (zero Mongo cost).
    Same tenant pre-filter as retrieve_far_clauses.
    """
    if not naics and not set_aside:
        return RelatedSolicitations(summaries=[], count=0)
    tenant_id = config["configurable"]["tenant_id"]
    try:
        docs = _query_related(tenant_id, naics, set_aside, k)
    except Exception as exc:  # non-fatal per design ref §3 stage 2
        log.warning("related-solicitation lookup failed (%s); continuing", exc)
        return RelatedSolicitations(summaries=[], count=0)
    summaries = [
        SolicitationSummary(
            solicitation_id=str(d.get("solicitation_id") or d.get("_id") or ""),
            title=d.get("title", ""),
            naics=d.get("naics"),
            set_aside=d.get("set_aside"),
            contract_type=d.get("contract_type"),
            award_status=d.get("award_status", "internal_review"),
            snapshot_date=d.get("snapshot_date") or _EPOCH,
        )
        for d in docs
    ]
    return RelatedSolicitations(summaries=summaries, count=len(summaries))
