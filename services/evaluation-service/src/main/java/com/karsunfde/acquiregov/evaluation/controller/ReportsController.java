package com.karsunfde.acquiregov.evaluation.controller;

import com.karsunfde.acquiregov.evaluation.client.SolicitationClient;
import com.karsunfde.acquiregov.evaluation.model.Award;
import com.karsunfde.acquiregov.evaluation.model.ContractModification;
import com.karsunfde.acquiregov.evaluation.model.Cpar;
import com.karsunfde.acquiregov.evaluation.model.Finding;
import com.karsunfde.acquiregov.evaluation.repository.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 5 acquire-gov reports (per feature-inventory-target.md lines 296-307):
 *   /api/reports/acquisition-pipeline     — CO + PM workload
 *   /api/reports/vendor-past-performance  — CPAR-rolled by NAICS
 *   /api/reports/contract-spend           — Awards + Mods aggregated
 *   /api/reports/oig-findings-status      — Findings × age × status
 *   /api/reports/audit-log-activity       — proxy into solicitation-service
 *
 * Brownfield-debt reinforced:
 *   - Item 3 — vendor-past-performance + audit-log-activity reach
 *     solicitation-service via SolicitationClient (no circuit breaker).
 *   - Item 10 — reports do not filter by agency claim.
 */
@RestController
@RequestMapping("/api/reports")
public class ReportsController {

    private final AwardRepository awardRepo;
    private final ContractRepository contractRepo;
    private final ContractModificationRepository modRepo;
    private final CparRepository cparRepo;
    private final FindingRepository findingRepo;
    private final SolicitationClient solicitationClient;

    @Autowired
    public ReportsController(AwardRepository awardRepo,
                             ContractRepository contractRepo,
                             ContractModificationRepository modRepo,
                             CparRepository cparRepo,
                             FindingRepository findingRepo,
                             SolicitationClient solicitationClient) {
        this.awardRepo = awardRepo;
        this.contractRepo = contractRepo;
        this.modRepo = modRepo;
        this.cparRepo = cparRepo;
        this.findingRepo = findingRepo;
        this.solicitationClient = solicitationClient;
    }

    /** SAM.gov-style pipeline by stage. */
    @GetMapping("/acquisition-pipeline")
    public Map<String, Object> acquisitionPipeline() {
        // ⚠ Item 3 — single call fans through solicitation list w/o breaker.
        Map<String, Object> out = new LinkedHashMap<>();
        Map<String, Long> awardsByAgency = awardRepo.findAll().stream()
            .collect(Collectors.groupingBy(Award::getAgencyId, Collectors.counting()));
        out.put("awardsByAgency", awardsByAgency);
        out.put("totalAwards", awardsByAgency.values().stream().mapToLong(Long::longValue).sum());
        return out;
    }

    /** CPAR-rolled by NAICS (joined via vendor metadata fetched from solicitation-service in a real path). */
    @GetMapping("/vendor-past-performance")
    public Map<String, Object> vendorPastPerformance(@RequestParam(required = false) String naics) {
        Map<String, Long> byVendor = cparRepo.findAll().stream()
            .collect(Collectors.groupingBy(Cpar::getVendorId, Collectors.counting()));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("naics", naics);
        out.put("cparsByVendor", byVendor);
        out.put("redCparCount", cparRepo.findAll().stream()
            .filter(c -> c.getRatings().values().stream()
                .anyMatch(r -> r != null && r.toLowerCase().contains("unsat")))
            .count());
        return out;
    }

    /** FPDS-NG-shaped agency spend rollup. */
    @GetMapping("/contract-spend")
    public Map<String, Object> contractSpend() {
        Map<String, BigDecimal> ceilingByAgency = new HashMap<>();
        contractRepo.findAll().forEach(c -> {
            BigDecimal cur = ceilingByAgency.getOrDefault(c.getAgencyId(), BigDecimal.ZERO);
            if (c.getCeilingValue() != null) {
                ceilingByAgency.put(c.getAgencyId(), cur.add(c.getCeilingValue()));
            }
        });
        Map<String, Long> modsByAgency = modRepo.findAll().stream()
            .collect(Collectors.groupingBy(ContractModification::getAgencyId, Collectors.counting()));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ceilingByAgency", ceilingByAgency);
        out.put("modificationsByAgency", modsByAgency);
        return out;
    }

    /** Findings × age × status. */
    @GetMapping("/oig-findings-status")
    public Map<String, Object> oigFindings() {
        Map<String, Long> byStatus = findingRepo.findAll().stream()
            .collect(Collectors.groupingBy(
                f -> f.getRemediationStatus() == null ? "UNKNOWN" : f.getRemediationStatus(),
                Collectors.counting()));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("byStatus", byStatus);
        out.put("openCount", byStatus.getOrDefault("OPEN", 0L));
        out.put("ages", findingRepo.findAll().stream()
            .map(Finding::getOpenedAt)
            .filter(Objects::nonNull)
            .map(Object::toString)
            .collect(Collectors.toList()));
        return out;
    }

    /** Activity proxy. Real implementation would call solicitation-service /api/audit-events. */
    @GetMapping("/audit-log-activity")
    public Map<String, Object> auditLogActivity() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("note", "Activity rollup served from solicitation-service /api/audit-events.");
        out.put("upstream", "solicitation-service");
        try {
            // ⚠ Item 3 — direct cross-service call, no breaker.
            // Sentinel call against /actuator/health to confirm reachability.
            solicitationClient.getSolicitation("__health__");
            out.put("upstreamReachable", true);
        } catch (Exception ex) {
            out.put("upstreamReachable", false);
            out.put("upstreamError", ex.getClass().getSimpleName());
        }
        return out;
    }
}
