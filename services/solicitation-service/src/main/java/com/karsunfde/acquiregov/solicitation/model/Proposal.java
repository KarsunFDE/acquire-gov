package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Vendor proposal submitted in response to a solicitation. Sealed until
 * solicitation closing deadline; visible to evaluators after CO unseals.
 *
 * ⚠ Item 2 — unseal is a multi-write transition; race with crash can leave
 * audit-log gap for SSDD-impacting event.
 * ⚠ Item 10 — proposals must be agency-scoped on list/read.
 */
@Document(collection = "proposals")
public class Proposal {

    @Id
    private String id;

    private String solicitationId;
    private String vendorId;
    private String agencyId;

    /** Volume I (Tech) / II (Past Perf) / III (Price) — stored as GridFS refs. */
    private List<String> volumes = new ArrayList<>();

    private String status; // DRAFT / SUBMITTED / SEALED / UNSEALED / WITHDRAWN
    private Instant submittedAt;
    private Instant sealedUntil;

    /** Numbers of amendments this proposal has acknowledged. */
    private List<Integer> acknowledgedAmendments = new ArrayList<>();

    public Proposal() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getSolicitationId() { return solicitationId; }
    public void setSolicitationId(String solicitationId) { this.solicitationId = solicitationId; }
    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public List<String> getVolumes() { return volumes; }
    public void setVolumes(List<String> volumes) { this.volumes = volumes; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getSubmittedAt() { return submittedAt; }
    public void setSubmittedAt(Instant submittedAt) { this.submittedAt = submittedAt; }
    public Instant getSealedUntil() { return sealedUntil; }
    public void setSealedUntil(Instant sealedUntil) { this.sealedUntil = sealedUntil; }
    public List<Integer> getAcknowledgedAmendments() { return acknowledgedAmendments; }
    public void setAcknowledgedAmendments(List<Integer> acknowledgedAmendments) { this.acknowledgedAmendments = acknowledgedAmendments; }
}
