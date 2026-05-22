package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/**
 * Solicitation document.
 *
 * ⚠ DELIBERATE — Item 10:
 *   {@code agencyId} is in the schema (so the data is multi-tenant-shaped) but
 *   the repository does not filter on it. Cohort fixes in W2 Wed multi-tenant
 *   retrieval-boundary work.
 *
 * ⚠ DELIBERATE — Item 9:
 *   {@code description} is not sanitized; arbitrary HTML accepted on write and
 *   returned verbatim on read. Cohort fixes in W4 Wed AI Security Engineering
 *   Day (prompt-injection-via-stored-content — description feeds the
 *   ai-orchestrator prompt).
 */
@Document(collection = "solicitations")
public class Solicitation {

    @Id
    private String id;

    /** ⚠ Item 10 — present but un-enforced. */
    private String agencyId;

    private String title;

    /** ⚠ Item 9 — accepts arbitrary HTML. */
    private String description;

    private String status;

    private Instant createdAt;
    private Instant updatedAt;

    public Solicitation() {}

    // --- getters / setters ---

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
