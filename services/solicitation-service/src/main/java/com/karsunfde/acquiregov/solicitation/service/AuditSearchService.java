package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.model.AuditEvent;
import com.karsunfde.acquiregov.solicitation.repository.AuditEventRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Backs the /admin/audit search view (sys_admin + oig_reviewer).
 *
 * ⚠ Item 2 — when the cohort searches by resource ID, missing rows from the
 * audit-log race surface as gaps in the result set. The "10 transitions, 8
 * audit rows" pattern is the canonical W5 AIOps detection signal.
 * ⚠ Item 6 — searching by correlationId returns inconsistent results because
 * each service writes a different key into the row.
 */
@Service
public class AuditSearchService {

    private final AuditEventRepository repo;

    @Autowired
    public AuditSearchService(AuditEventRepository repo) {
        this.repo = repo;
    }

    public List<AuditEvent> search(String actor, String resourceType, String resourceId,
                                    String correlationId, String action,
                                    Instant from, Instant to, String agencyId) {
        List<AuditEvent> base;
        if (resourceType != null && resourceId != null) {
            base = repo.findByResourceTypeAndResourceId(resourceType, resourceId);
        } else if (correlationId != null) {
            base = repo.findByCorrelationId(correlationId);
        } else if (actor != null) {
            base = repo.findByActor(actor);
        } else if (action != null) {
            base = repo.findByAction(action);
        } else if (agencyId != null && from != null && to != null) {
            base = repo.findByAgencyIdAndTimestampBetween(agencyId, from, to);
        } else {
            base = repo.findAll();
        }
        return base.stream()
            .filter(e -> actor == null || actor.equals(e.getActor()))
            .filter(e -> action == null || action.equals(e.getAction()))
            .filter(e -> agencyId == null || agencyId.equals(e.getAgencyId()))
            .collect(Collectors.toList());
    }

    /** CSV export hook — returns rows that would be in the export. */
    public List<AuditEvent> export(String actor, String resourceType, String resourceId,
                                   String correlationId, String action,
                                   Instant from, Instant to, String agencyId) {
        return search(actor, resourceType, resourceId, correlationId, action, from, to, agencyId);
    }
}
