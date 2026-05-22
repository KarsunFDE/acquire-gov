package com.karsunfde.acquiregov.solicitation.audit;

import com.karsunfde.acquiregov.solicitation.model.AuditEvent;
import com.karsunfde.acquiregov.solicitation.repository.AuditEventRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * Audit logger.
 *
 * ⚠ DELIBERATE — Item 2 in docs/brownfield-debt.md ⚠
 *
 * {@code recordAsync} is the only path callers use. It runs on Spring's
 * default async executor — which means:
 *
 *   1. The HTTP response is flushed BEFORE the audit row is written
 *      (the controller returns; the async task runs on a separate thread).
 *   2. There is NO {@code @Transactional} on the async path — even if the
 *      caller is inside a transaction, this lives outside it.
 *   3. If the service crashes between flush and async-write, the audit row
 *      is lost forever. The CRUD operation succeeded, but there's no
 *      audit-trail evidence of it.
 *
 * Cohort finds this in W3 multi-agent HITL audit-trail work + W5 Wed AIOps
 * governance via a crash-drill.
 *
 * What "fixed" looks like:
 *   - Synchronous + transactional write in the same boundary as the CRUD op
 *     (transactional outbox preferred so external-system audit sinks stay
 *     consistent).
 */
@Component
public class AuditLogger {

    private static final Logger log = LoggerFactory.getLogger(AuditLogger.class);

    private final AuditEventRepository repo;

    @Autowired
    public AuditLogger(AuditEventRepository repo) {
        this.repo = repo;
    }

    /**
     * ⚠ Async = runs AFTER response is flushed.
     *
     * The "Async" was added when ops complained that audit writes were adding
     * 40ms to p99 latency. It "fixed" the latency. It also created Item 2.
     */
    @Async
    public void recordAsync(String action, String resourceType, String resourceId,
                            String actor, String agencyId) {
        try {
            AuditEvent event = new AuditEvent(action, resourceType, resourceId, actor, agencyId);
            repo.save(event);
            // Item 6 — solicitation-service uses correlationId key.
            log.info("audit-write action={} resource={}:{} actor={} agencyId={} correlationId=N/A",
                action, resourceType, resourceId, actor, agencyId);
        } catch (Exception e) {
            log.error("audit-write FAILED (will be lost) action={} resource={}:{}",
                action, resourceType, resourceId, e);
        }
    }
}
