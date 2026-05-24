package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Contractor Performance Assessment Report. FAR 42.15. CPARS-shaped.
 *
 * ⚠ Item 9 — {@code vendorRebuttal} accepts raw HTML; cohort fixes W4 Wed.
 */
@Document(collection = "cpars")
public class Cpar {

    @Id
    private String id;

    private String contractId;
    private String agencyId;
    private String vendorId;
    private String period; // INTERIM / FINAL

    /** Quality / Schedule / Cost Control / Management / Small Business / Reg. Compliance. */
    private Map<String, String> ratings = new HashMap<>();

    private String narrative;
    /** ⚠ Item 9 — raw HTML accepted. */
    private String vendorRebuttal;
    private String status; // DRAFT / SUBMITTED / REBUTTAL_PENDING / FINALIZED
    private Instant draftedAt;
    private Instant rebuttalDueAt;
    private Instant finalizedAt;

    public Cpar() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getContractId() { return contractId; }
    public void setContractId(String contractId) { this.contractId = contractId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
    public String getPeriod() { return period; }
    public void setPeriod(String period) { this.period = period; }
    public Map<String, String> getRatings() { return ratings; }
    public void setRatings(Map<String, String> ratings) { this.ratings = ratings; }
    public String getNarrative() { return narrative; }
    public void setNarrative(String narrative) { this.narrative = narrative; }
    public String getVendorRebuttal() { return vendorRebuttal; }
    public void setVendorRebuttal(String vendorRebuttal) { this.vendorRebuttal = vendorRebuttal; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getDraftedAt() { return draftedAt; }
    public void setDraftedAt(Instant draftedAt) { this.draftedAt = draftedAt; }
    public Instant getRebuttalDueAt() { return rebuttalDueAt; }
    public void setRebuttalDueAt(Instant rebuttalDueAt) { this.rebuttalDueAt = rebuttalDueAt; }
    public Instant getFinalizedAt() { return finalizedAt; }
    public void setFinalizedAt(Instant finalizedAt) { this.finalizedAt = finalizedAt; }
}
