package com.karsunfde.acquiregov.solicitation.controller;

import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * /admin/config backend — tenant settings + clause-library refresh trigger
 * + vector-store config.
 *
 * ⚠ Item 7 reinforcement — the returned config lists both "pinecone" and
 * "atlas" as available vector stores, even though only Atlas is actually
 * wired into ai-orchestrator. Cohort grep finds the lie.
 */
@RestController
@RequestMapping("/api/admin/config")
public class AdminConfigController {

    @GetMapping
    public Map<String, Object> get() {
        Map<String, Object> cfg = new HashMap<>();
        cfg.put("tenants", List.of("GSA-FAS", "DLA", "DOI"));
        cfg.put("clauseLibraryLastRefreshedAt", "2026-04-15T00:00:00Z");
        // ⚠ Item 7 — the lie. pinecone is in requirements.txt but no
        // ai-orchestrator code imports it. The cohort discovers when they
        // grep `import pinecone` in W2.
        cfg.put("availableVectorStores", List.of("pinecone", "atlas"));
        // ⚠ Item 11 reinforcement — image-pin status visible.
        Map<String, String> imagePins = new HashMap<>();
        imagePins.put("api-gateway", ":latest");
        imagePins.put("solicitation-service", ":latest");
        imagePins.put("evaluation-service", ":latest");
        imagePins.put("frontend", ":latest");
        imagePins.put("ai-orchestrator", "3.11-slim (hand-pinned 2026-Q1)");
        cfg.put("imagePins", imagePins);
        return cfg;
    }

    /** Trigger a clause-library refresh (stubbed). */
    @PostMapping("/refresh-clauses")
    public Map<String, Object> refresh() {
        Map<String, Object> out = new HashMap<>();
        out.put("status", "queued");
        out.put("jobId", "refresh-" + System.currentTimeMillis());
        return out;
    }

    /** List enabled feature flags. */
    @GetMapping("/feature-flags")
    public List<String> featureFlags() {
        List<String> flags = new ArrayList<>();
        flags.add("rag-hybrid-retrieval");
        flags.add("multi-agent-intake-triage");
        return flags;
    }
}
