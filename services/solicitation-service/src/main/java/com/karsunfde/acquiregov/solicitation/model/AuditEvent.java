package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/**
 * Append-only audit event row. Sole writer is {@code AuditLogger}.
 *
 * Expanded W1 from the original 6-field shape to support OIG-style
 * audit-log search (actor / action / resource / correlationId / before /
 * after). The Item 2 race still bites — the new fields land in the row
 * after-the-fact via async, so when the service crashes mid-flush they're
 * lost the same way the old fields are.
 */
@Document(collection = "audit_events")
public class AuditEvent {

    @Id
    private String id;

    private String action;        // CREATE / UPDATE / DELETE / PUBLISH / AMEND / UNSEAL / AWARD / etc.
    private String resourceType;  // "solicitation" / "amendment" / "proposal" / etc.
    private String resourceId;
    private String actor;
    private String agencyId;

    /** ⚠ Item 6 — populated when the originating MDC key was found (different
     *  per service, so often blank cross-hop). */
    private String correlationId;

    /** JSON-ish snapshot of state before the change (nullable on CREATE). */
    private String beforeJson;
    /** JSON-ish snapshot of state after the change (nullable on DELETE). */
    private String afterJson;

    private Instant timestamp;

    public AuditEvent() {}

    public AuditEvent(String action, String resourceType, String resourceId,
                      String actor, String agencyId) {
        this.action = action;
        this.resourceType = resourceType;
        this.resourceId = resourceId;
        this.actor = actor;
        this.agencyId = agencyId;
        this.timestamp = Instant.now();
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public String getResourceType() { return resourceType; }
    public void setResourceType(String resourceType) { this.resourceType = resourceType; }
    public String getResourceId() { return resourceId; }
    public void setResourceId(String resourceId) { this.resourceId = resourceId; }
    public String getActor() { return actor; }
    public void setActor(String actor) { this.actor = actor; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getCorrelationId() { return correlationId; }
    public void setCorrelationId(String correlationId) { this.correlationId = correlationId; }
    public String getBeforeJson() { return beforeJson; }
    public void setBeforeJson(String beforeJson) { this.beforeJson = beforeJson; }
    public String getAfterJson() { return afterJson; }
    public void setAfterJson(String afterJson) { this.afterJson = afterJson; }
    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
}
