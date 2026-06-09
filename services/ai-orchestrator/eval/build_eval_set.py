"""Corpus → eval-set generator for M2 grounded retrieval.

Per docs/specs/m2-eval-harness.md §3.1. Reads the FAR snapshot +
synthetic-solicitations directories, emits 2-3 structurally-derived queries
per discovered FAR section. The corpus IS the ground truth — clause-lookup
queries know which clause answers them by structure, not opinion. This
structurally avoids anti-pattern #9 in ADR-0009 D5 (eval written by the
same engineers tuning prompts).

CLI:
    python -m eval.build_eval_set \
        --far-dir docs/reference/far \
        --solicitations-dir docs/reference/synthetic-solicitations \
        --out services/ai-orchestrator/eval/far_eval_set.jsonl

Robustness: if either input dir is absent (other agent's work still in
flight in a sibling worktree) the script writes an empty .jsonl + a stderr
warning rather than crashing — the harness is wired before the corpus is.
The first real eval-set build runs once C1 (FAR snapshot) and the corpus
spec's seed PRs have merged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

# FAR Part 15.2 + Part 52 are the lean-corpus scope (ADR-0005 D4).
# FAR section IDs in Part 52 look like "52.212-4" or "52.219-14".
FAR_CLAUSE_RE = re.compile(r"\b(5[0-9])\.\s?(\d{2,3})(?:-(\d{1,3}))?\b")

# FAR Part 15.2 subsection IDs look like "15.201", "15.203", "15.207".
FAR_SUBSECTION_RE = re.compile(r"\b(1[0-9])\.(\d{3})\b")

# UCF section letters per FAR 15.204 — used for section-scoped queries.
UCF_SECTIONS = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M")


@dataclass(frozen=True)
class EvalCase:
    eval_id: str
    query: str
    expected_far_section_ids: tuple[str, ...]
    expected_chunk_ids: tuple[str, ...]  # populated post-ingest; empty at build time
    expected_answer_summary: str
    tenant_id: str
    category: str

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "eval_id": self.eval_id,
                "query": self.query,
                "expected_far_section_ids": list(self.expected_far_section_ids),
                "expected_chunk_ids": list(self.expected_chunk_ids),
                "expected_answer_summary": self.expected_answer_summary,
                "tenant_id": self.tenant_id,
                "category": self.category,
            },
            ensure_ascii=False,
        )


def _iter_markdown_files(root: Path) -> Iterator[Path]:
    """Yield every *.md file under root, ignoring MANIFEST tombstones."""
    if not root.exists() or not root.is_dir():
        return
    for p in sorted(root.rglob("*.md")):
        if p.name.startswith("MANIFEST"):
            continue
        yield p


def _extract_far_clauses(text: str) -> list[str]:
    """Return distinct FAR Part 52 clause IDs mentioned in text.

    Examples: "52.212-4", "52.219-14". Preserves discovery order so the
    eval-set is reproducible across runs.
    """
    seen: dict[str, None] = {}
    for m in FAR_CLAUSE_RE.finditer(text):
        part, sec, sub = m.group(1), m.group(2), m.group(3)
        clause = f"{part}.{sec}" + (f"-{sub}" if sub else "")
        if clause not in seen:
            seen[clause] = None
    return list(seen.keys())


def _extract_far_subsections(text: str) -> list[str]:
    """Return distinct FAR Part 15.2 subsection IDs mentioned in text."""
    seen: dict[str, None] = {}
    for m in FAR_SUBSECTION_RE.finditer(text):
        part, sub = m.group(1), m.group(2)
        # Only Part 15 in the lean corpus scope.
        if part == "15":
            sid = f"{part}.{sub}"
            if sid not in seen:
                seen[sid] = None
    return list(seen.keys())


def _section_titles(text: str) -> list[tuple[str, str]]:
    """Return [(section_id, heading_text)] discovered in markdown.

    Heuristic: ATX-style "### 52.212-4  Contract Terms..." or
    "### 15.203 Requests for proposals". We pair the first matching
    FAR id on the heading line with the heading text.
    """
    titles: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        body = stripped.lstrip("#").strip()
        clauses = _extract_far_clauses(body)
        subsections = _extract_far_subsections(body)
        if clauses:
            titles.append((clauses[0], body))
        elif subsections:
            titles.append((subsections[0], body))
    return titles


def _heading_title_only(heading: str, far_id: str) -> str:
    """Strip the FAR id prefix from a markdown heading, return remaining title."""
    rest = heading
    # Heuristic: strip first occurrence of the id and surrounding whitespace/dashes.
    rest = re.sub(re.escape(far_id) + r"[\s\-:—]*", "", rest, count=1).strip()
    return rest or heading


def _queries_for_far_section(
    far_id: str, heading: str, source_path: Path, eval_id_counter: Iterator[int]
) -> list[EvalCase]:
    """Emit 2-3 queries per FAR section per spec §3.1 rule.

    1. clause-lookup       — "What does FAR <id> say?"
    2. semantic-paraphrase — natural-language rendering of the title
    3. section-scoped      — UCF letter-scoped if heading is a clause (Part 52)
    """
    title = _heading_title_only(heading, far_id)
    cases: list[EvalCase] = []

    # 1. Clause-lookup
    cases.append(
        EvalCase(
            eval_id=f"EV-{next(eval_id_counter):04d}",
            query=f"What does FAR {far_id} say about {title.lower() or 'this clause'}?"
            if title
            else f"What does FAR {far_id} say?",
            expected_far_section_ids=(far_id,),
            expected_chunk_ids=(),
            expected_answer_summary=(
                f"Reference answer should cite FAR {far_id} ({title or 'clause text'})."
            ),
            tenant_id="agency-test",
            category="clause-lookup",
        )
    )

    # 2. Semantic-paraphrase — derived from heading title only (no opinion).
    if title:
        cases.append(
            EvalCase(
                eval_id=f"EV-{next(eval_id_counter):04d}",
                query=f"Where in the FAR are the requirements for {title.lower()}?",
                expected_far_section_ids=(far_id,),
                expected_chunk_ids=(),
                expected_answer_summary=(
                    f"Reference answer should cite FAR {far_id} as the locating regulation."
                ),
                tenant_id="agency-test",
                category="semantic-prose",
            )
        )

    # 3. Section-scoped — applies when the FAR id is a Part 52 clause; we ask
    # which UCF Section I-style location it would appear in. Section I covers
    # Contract Clauses per FAR 15.204.
    if FAR_CLAUSE_RE.fullmatch(far_id) or "-" in far_id:
        cases.append(
            EvalCase(
                eval_id=f"EV-{next(eval_id_counter):04d}",
                query=(
                    f"Within a solicitation's UCF Section I (Contract Clauses), "
                    f"summarize the application of FAR {far_id}."
                ),
                expected_far_section_ids=(far_id,),
                expected_chunk_ids=(),
                expected_answer_summary=(
                    f"Reference answer should cite FAR {far_id} located in UCF Section I."
                ),
                tenant_id="agency-test",
                category="section-scoped",
            )
        )

    return cases


def _cross_section_queries(
    all_far_ids: list[str], eval_id_counter: Iterator[int]
) -> list[EvalCase]:
    """Emit a small number of cross-section queries spanning two FAR ids.

    The list is sliced deterministically (no randomness) to keep eval-set
    builds reproducible across runs.
    """
    cases: list[EvalCase] = []
    # Pair adjacent FAR ids (deterministic) — keeps cross-section count
    # bounded by corpus size, no manual selection.
    pairs = list(zip(all_far_ids[::2], all_far_ids[1::2]))[:5]
    for a, b in pairs:
        cases.append(
            EvalCase(
                eval_id=f"EV-{next(eval_id_counter):04d}",
                query=f"Compare the requirements in FAR {a} and FAR {b}.",
                expected_far_section_ids=(a, b),
                expected_chunk_ids=(),
                expected_answer_summary=(
                    f"Reference answer should cite both FAR {a} and FAR {b}."
                ),
                tenant_id="agency-test",
                category="cross-section",
            )
        )
    return cases


def build_eval_cases(
    far_dir: Path,
    solicitations_dir: Path,
) -> list[EvalCase]:
    """Generate the structural eval set from FAR + solicitation markdown.

    Robustness contract (spec §3.1, this script's docstring):
    - Missing FAR dir          → empty cases + stderr warning
    - Missing solicitations dir → FAR-only eval set + stderr warning
    """
    if not far_dir.exists():
        print(
            f"[build_eval_set] WARNING: FAR dir {far_dir} not found; emitting empty eval set. "
            "First real build runs once C1 (FAR snapshot) is merged.",
            file=sys.stderr,
        )
        return []

    counter = iter(range(1, 100_000))
    cases: list[EvalCase] = []
    seen_far_ids: dict[str, None] = {}

    # FAR snapshot — primary structural-ground-truth source.
    for md_path in _iter_markdown_files(far_dir):
        text = md_path.read_text(encoding="utf-8", errors="replace")
        for far_id, heading in _section_titles(text):
            if far_id in seen_far_ids:
                continue
            seen_far_ids[far_id] = None
            cases.extend(_queries_for_far_section(far_id, heading, md_path, counter))

    # Synthetic solicitations — add semantic-prose queries that cite FAR clauses
    # the solicitation references. These exercise cross-doc retrieval.
    if solicitations_dir.exists():
        for md_path in _iter_markdown_files(solicitations_dir):
            text = md_path.read_text(encoding="utf-8", errors="replace")
            for far_id in _extract_far_clauses(text):
                # Only emit a query if the FAR id was already seen in the FAR
                # snapshot — guarantees ground-truth chunks exist post-ingest.
                if far_id not in seen_far_ids:
                    continue
                cases.append(
                    EvalCase(
                        eval_id=f"EV-{next(counter):04d}",
                        query=(
                            f"In the context of a federal solicitation, what is the role "
                            f"of FAR {far_id}?"
                        ),
                        expected_far_section_ids=(far_id,),
                        expected_chunk_ids=(),
                        expected_answer_summary=(
                            f"Reference answer should cite FAR {far_id} and explain its "
                            "applicability within the solicitation."
                        ),
                        tenant_id="agency-test",
                        category="semantic-prose",
                    )
                )
    else:
        print(
            f"[build_eval_set] WARNING: solicitations dir {solicitations_dir} not found; "
            "skipping solicitation-derived queries.",
            file=sys.stderr,
        )

    # Cross-section queries — sliced deterministically from discovered FAR ids.
    if len(seen_far_ids) >= 2:
        cases.extend(_cross_section_queries(list(seen_far_ids), counter))

    return cases


def write_jsonl(cases: Iterable[EvalCase], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(case.to_jsonl())
            fh.write("\n")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--far-dir",
        type=Path,
        default=Path("docs/reference/far"),
        help="FAR markdown snapshot dir (ADR-0011 D7). Default: docs/reference/far",
    )
    parser.add_argument(
        "--solicitations-dir",
        type=Path,
        default=Path("docs/reference/synthetic-solicitations"),
        help="Synthetic solicitations dir. Default: docs/reference/synthetic-solicitations",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("services/ai-orchestrator/eval/far_eval_set.jsonl"),
        help="Output JSONL path.",
    )
    args = parser.parse_args(argv)

    cases = build_eval_cases(args.far_dir, args.solicitations_dir)
    n = write_jsonl(cases, args.out)
    print(f"[build_eval_set] wrote {n} cases → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
