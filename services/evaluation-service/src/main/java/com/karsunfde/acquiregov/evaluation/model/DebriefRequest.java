package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/**
 * Unsuccessful-offeror debrief request. FAR 15.506 — 5-day window.
 *
 * ⚠ Item 9 — {@code narrative} carries the raw vendor-supplied debrief
 * request text; sanitization fix lands W4 Wed.
 */
@Document(collection = "debrief_requests")
public class DebriefRequest {

    @Id
    private String id;

    private String awardId;
    private String vendorId;
    private String agencyId;
    /** ⚠ Item 9 — raw HTML accepted. */
    private String narrative;
    private String status; // PENDING / SCHEDULED / COMPLETED
    private Instant requestedAt;

    public DebriefRequest() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getAwardId() { return awardId; }
    public void setAwardId(String awardId) { this.awardId = awardId; }
    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getNarrative() { return narrative; }
    public void setNarrative(String narrative) { this.narrative = narrative; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getRequestedAt() { return requestedAt; }
    public void setRequestedAt(Instant requestedAt) { this.requestedAt = requestedAt; }
}
