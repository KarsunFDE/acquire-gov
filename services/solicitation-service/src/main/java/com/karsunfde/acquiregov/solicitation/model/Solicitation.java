package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Solicitation document. Expanded W1 (was just id/title/description/status)
 * to the full FAR 15.204 Section A-M shape — drives the cohort's W1 Tue
 * inventory walkthrough.
 *
 * ⚠ DELIBERATE — Item 10:
 *   {@code agencyId} is in the schema (so the data is multi-tenant-shaped)
 *   but the repository does not filter on it. Cohort fixes in W2 Wed
 *   multi-tenant retrieval-boundary work.
 *
 * ⚠ DELIBERATE — Item 9:
 *   {@code description} is not sanitized; arbitrary HTML accepted on write
 *   and returned verbatim on read. Cohort fixes in W4 Wed AI Security
 *   Engineering Day (prompt-injection-via-stored-content — description
 *   feeds the ai-orchestrator prompt). New W1 fields {@code sections}
 *   carry the same un-sanitized-text debt.
 *
 * State machine (Workflow 1):
 *   DRAFT -> INTERNAL_REVIEW -> READY_TO_PUBLISH -> PUBLISHED -> (AMENDED)* -> CLOSED
 *   CANCELLED is reachable from any pre-PUBLISHED state.
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

    /** NAICS code, e.g., 541512. */
    private String naics;
    /** Set-aside category (e.g., 8(a), WOSB, SDVOSB, none). */
    private String setAside;

    /**
     * Sections A-M (FAR 15.204 RFP structure). Stored as JSON-ish map so the
     * cohort can extend without schema changes. ⚠ Item 9 — values
     * unsanitized; feeds /draft-solicitation + /draft-amendment prompts.
     */
    private Map<String, String> sections = new HashMap<>();

    private Instant postedAt;
    private Instant closingAt;
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

    public String getNaics() { return naics; }
    public void setNaics(String naics) { this.naics = naics; }

    public String getSetAside() { return setAside; }
    public void setSetAside(String setAside) { this.setAside = setAside; }

    public Map<String, String> getSections() { return sections; }
    public void setSections(Map<String, String> sections) { this.sections = sections; }

    public Instant getPostedAt() { return postedAt; }
    public void setPostedAt(Instant postedAt) { this.postedAt = postedAt; }

    public Instant getClosingAt() { return closingAt; }
    public void setClosingAt(Instant closingAt) { this.closingAt = closingAt; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
