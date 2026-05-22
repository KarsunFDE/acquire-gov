package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/** Append-only audit event row. Sole writer is {@code AuditLogger}. */
@Document(collection = "audit_events")
public class AuditEvent {

    @Id
    private String id;

    private String action;        // CREATE / UPDATE / DELETE
    private String resourceType;  // "solicitation"
    private String resourceId;
    private String actor;
    private String agencyId;
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
    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }
}
