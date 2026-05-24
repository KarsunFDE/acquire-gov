package com.karsunfde.acquiregov.solicitation.dto;

/**
 * Amendment issuance DTO.
 *
 * ⚠ Item 9 — {@code changeSummary} accepts raw HTML; feeds /draft-amendment
 * via the ai-orchestrator.
 */
public class AmendmentRequest {
    private String changeSummary;
    private boolean requiresAcknowledgement;
    private String effectiveAt;

    public AmendmentRequest() {}

    public String getChangeSummary() { return changeSummary; }
    public void setChangeSummary(String changeSummary) { this.changeSummary = changeSummary; }
    public boolean isRequiresAcknowledgement() { return requiresAcknowledgement; }
    public void setRequiresAcknowledgement(boolean requiresAcknowledgement) { this.requiresAcknowledgement = requiresAcknowledgement; }
    public String getEffectiveAt() { return effectiveAt; }
    public void setEffectiveAt(String effectiveAt) { this.effectiveAt = effectiveAt; }
}
