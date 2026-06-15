"""Part III (Section J) wizard-passthrough adapter (ADR-0014 D4).

No LLM. The wizard already collected the attachment metadata; the coordinator
just shapes it into a PartResult so the bundle's four Parts are uniform.
"""
from __future__ import annotations

from app.agents.schemas import PartIIIAttachmentMeta, PartResult


def pass_through_part_iii(attachments: list[PartIIIAttachmentMeta]) -> PartResult:
    return PartResult(
        part="III",
        kind="wizard_provided",
        sections={"J": list(attachments)},
    )
