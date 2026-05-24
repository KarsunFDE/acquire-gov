package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.AuditEvent;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.time.Instant;
import java.util.List;

public interface AuditEventRepository extends MongoRepository<AuditEvent, String> {

    List<AuditEvent> findByActor(String actor);

    List<AuditEvent> findByResourceTypeAndResourceId(String resourceType, String resourceId);

    List<AuditEvent> findByAction(String action);

    /** ⚠ Item 6 — correlationId is rarely set cross-service; this query
     *  returns half-empty results when the cohort searches via the admin UI. */
    List<AuditEvent> findByCorrelationId(String correlationId);

    List<AuditEvent> findByAgencyIdAndTimestampBetween(String agencyId, Instant from, Instant to);
}
