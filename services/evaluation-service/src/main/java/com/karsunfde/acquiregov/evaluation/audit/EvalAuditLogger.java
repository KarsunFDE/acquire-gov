package com.karsunfde.acquiregov.evaluation.audit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * Local async audit emitter for evaluation-service. Mirrors the
 * solicitation-service Item 2 pattern — log-only fan-out here (no separate
 * Mongo collection in this service; the canonical audit_events collection
 * lives in solicitation-service and would be reached via cross-service call
 * once the cohort wires that path post-fix).
 *
 * Brownfield-debt items reinforced:
 *   - Item 2 — async fire-and-forget; can be lost on crash.
 *   - Item 6 — logs traceId key (mismatched with solicitation-service +
 *     api-gateway).
 */
@Component
public class EvalAuditLogger {

    private static final Logger log = LoggerFactory.getLogger(EvalAuditLogger.class);

    @Async
    public void recordAsync(String action, String resourceType, String resourceId,
                            String actor, String agencyId) {
        // ⚠ Item 6 — traceId key, not correlationId / X-Request-ID.
        log.info("eval-audit action={} resource={}:{} actor={} agencyId={} traceId=N/A",
            action, resourceType, resourceId, actor, agencyId);
    }
}
