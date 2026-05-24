package com.karsunfde.acquiregov.solicitation.controller;

import com.karsunfde.acquiregov.solicitation.model.AuditEvent;
import com.karsunfde.acquiregov.solicitation.service.AuditSearchService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;

/**
 * Audit-log search + CSV export. Backs the /admin/audit view.
 *
 * ⚠ Item 2 — search results show race-related gaps.
 * ⚠ Item 6 — correlationId search yields half-empty results.
 */
@RestController
@RequestMapping("/api/audit-events")
public class AuditController {

    private final AuditSearchService svc;

    @Autowired
    public AuditController(AuditSearchService svc) {
        this.svc = svc;
    }

    @GetMapping
    public List<AuditEvent> search(@RequestParam(required = false) String actor,
                                    @RequestParam(required = false) String resourceType,
                                    @RequestParam(required = false) String resourceId,
                                    @RequestParam(required = false) String correlationId,
                                    @RequestParam(required = false) String action,
                                    @RequestParam(required = false) String agencyId,
                                    @RequestParam(required = false) String from,
                                    @RequestParam(required = false) String to) {
        Instant fromI = from != null ? Instant.parse(from) : null;
        Instant toI = to != null ? Instant.parse(to) : null;
        return svc.search(actor, resourceType, resourceId, correlationId,
            action, fromI, toI, agencyId);
    }

    @PostMapping(value = "/export", produces = "text/csv")
    public ResponseEntity<String> export(@RequestParam(required = false) String actor,
                                          @RequestParam(required = false) String resourceType,
                                          @RequestParam(required = false) String resourceId,
                                          @RequestParam(required = false) String correlationId,
                                          @RequestParam(required = false) String action,
                                          @RequestParam(required = false) String agencyId,
                                          @RequestParam(required = false) String from,
                                          @RequestParam(required = false) String to) {
        Instant fromI = from != null ? Instant.parse(from) : null;
        Instant toI = to != null ? Instant.parse(to) : null;
        List<AuditEvent> rows = svc.export(actor, resourceType, resourceId,
            correlationId, action, fromI, toI, agencyId);
        StringBuilder csv = new StringBuilder(
            "id,timestamp,actor,action,resourceType,resourceId,agencyId,correlationId\n");
        for (AuditEvent e : rows) {
            csv.append(safe(e.getId())).append(',')
               .append(e.getTimestamp() == null ? "" : e.getTimestamp().toString()).append(',')
               .append(safe(e.getActor())).append(',')
               .append(safe(e.getAction())).append(',')
               .append(safe(e.getResourceType())).append(',')
               .append(safe(e.getResourceId())).append(',')
               .append(safe(e.getAgencyId())).append(',')
               .append(safe(e.getCorrelationId())).append('\n');
        }
        return ResponseEntity.ok()
            .contentType(MediaType.parseMediaType("text/csv"))
            .body(csv.toString());
    }

    private static String safe(String v) {
        if (v == null) return "";
        // ⚠ Item 9 reinforcement — the CSV escape strategy is naive; HTML
        // tags in actor/action fields pass through verbatim.
        return v.replace(",", " ");
    }
}
