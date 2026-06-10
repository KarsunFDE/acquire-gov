"""C2 — retrieval-side splitter tests.

Spec: docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §5 (module layout).
Confirms ``app.retrieval_chunks.split_markdown`` produces chunks carrying
``far_part`` / ``far_section`` metadata for downstream embedding +
hybrid-search filtering (ADR-0008 D2 tenant filter sits on top of these).
"""
from __future__ import annotations

from app import retrieval_chunks


_PART_15_SAMPLE = (
    "# FAR Part 15\n"
    "## 15.201 Exchanges with industry\n"
    "Body text for 15.201 — describes pre-proposal exchanges.\n"
    "## 15.206 Amending the solicitation\n"
    "Body text for 15.206 — describes when to amend.\n"
    "### 15.206-1 Distribution\n"
    "Subsection body for distribution rules.\n"
)


def test_split_markdown_returns_chunks_with_far_part_metadata() -> None:
    chunks = retrieval_chunks.split_markdown(_PART_15_SAMPLE)
    assert chunks, "splitter returned no chunks"
    parts = {c.get("far_part") for c in chunks if c.get("far_part")}
    assert parts, f"no far_part metadata on any chunk: {chunks}"
    assert any("Part 15" in p for p in parts)


def test_split_markdown_carries_far_section_into_sub_chunks() -> None:
    chunks = retrieval_chunks.split_markdown(_PART_15_SAMPLE)
    sections = {c.get("far_section") for c in chunks if c.get("far_section")}
    assert "15.201 Exchanges with industry" in sections
    assert "15.206 Amending the solicitation" in sections


def test_split_markdown_preserves_subsection() -> None:
    chunks = retrieval_chunks.split_markdown(_PART_15_SAMPLE)
    subs = {c.get("far_subsection") for c in chunks if c.get("far_subsection")}
    assert any("Distribution" in s for s in subs if s), \
        f"expected 15.206-1 subsection chunk; got: {subs}"


def test_split_markdown_chunk_index_is_sequential() -> None:
    chunks = retrieval_chunks.split_markdown(_PART_15_SAMPLE)
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_split_markdown_respects_chunk_size_kwarg() -> None:
    big = "# Part X\n## Section Y\n" + ("word " * 1000)
    small_chunks = retrieval_chunks.split_markdown(big, chunk_size=200, chunk_overlap=20)
    # 5000+ chars under chunk_size=200 must produce > 1 sub-chunk
    assert len(small_chunks) > 1
    for c in small_chunks:
        assert len(c["text"]) <= 250  # chunk_size + some overlap-related slack


def test_split_markdown_empty_input_returns_empty() -> None:
    assert retrieval_chunks.split_markdown("") == []
    assert retrieval_chunks.split_markdown("   \n  \n") == []
