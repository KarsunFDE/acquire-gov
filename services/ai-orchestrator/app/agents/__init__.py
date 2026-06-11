"""M1 agentic drafting package (ADR-0012/0013/0014/0015).

Sub-modules:
- ``schemas``      — every cross-phase Pydantic model (Phase 0)
- ``checkpointer`` — MongoDBSaver singleton + thread_id helpers (Phase 0)
- ``builder``      — build_section_drafter_agent (Phase 1)
- ``prompts``      — system prompts (Phase 1)
- ``middleware``   — HITL gate middleware (Phase 2)
- ``tools``        — programmatic + LLM tools (Phase 1)
"""
