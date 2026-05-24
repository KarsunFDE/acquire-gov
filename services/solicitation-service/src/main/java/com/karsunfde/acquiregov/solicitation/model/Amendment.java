package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/**
 * Amendment to a published solicitation. FAR 15.206.
 *
 * Amendments are numbered sequentially per solicitation (0001, 0002, ...).
 * Vendors with proposals-in-progress must acknowledge before deadline.
 *
 * ⚠ Item 9 — {@code changeSummary} is raw HTML, fed into ai-orchestrator
 * for /draft-amendment narrative generation.
 * ⚠ Item 2 — amendment state transitions are audit-log race-prone.
 */
@Document(collection = "amendments")
public class Amendment {

    @Id
    private String id;

    private String solicitationId;
    private String agencyId;
    private int number;

    /** ⚠ Item 9 — raw HTML accepted. */
    private String changeSummary;

    private Instant effectiveAt;
    private boolean requiresAcknowledgement;
    private Instant createdAt;

    public Amendment() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getSolicitationId() { return solicitationId; }
    public void setSolicitationId(String solicitationId) { this.solicitationId = solicitationId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public int getNumber() { return number; }
    public void setNumber(int number) { this.number = number; }
    public String getChangeSummary() { return changeSummary; }
    public void setChangeSummary(String changeSummary) { this.changeSummary = changeSummary; }
    public Instant getEffectiveAt() { return effectiveAt; }
    public void setEffectiveAt(Instant effectiveAt) { this.effectiveAt = effectiveAt; }
    public boolean isRequiresAcknowledgement() { return requiresAcknowledgement; }
    public void setRequiresAcknowledgement(boolean requiresAcknowledgement) { this.requiresAcknowledgement = requiresAcknowledgement; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
