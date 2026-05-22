package com.karsunfde.acquiregov.evaluation.controller;

import com.karsunfde.acquiregov.evaluation.client.SolicitationClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Evaluation panel coordination endpoints.
 *
 * ⚠ DELIBERATE — Item 3 reinforcement:
 *   POST /api/evaluations is a state-mutating endpoint that does NOT accept
 *   or honour an Idempotency-Key header. A retry from the client creates
 *   duplicate evaluations.
 */
@RestController
@RequestMapping("/api/evaluations")
public class EvaluationController {

    private final SolicitationClient solicitationClient;

    @Autowired
    public EvaluationController(SolicitationClient solicitationClient) {
        this.solicitationClient = solicitationClient;
    }

    /** Fetch the solicitation snapshot the evaluation panel is reviewing. */
    @GetMapping("/{evaluationId}/solicitation/{solicitationId}")
    public ResponseEntity<Map<String, Object>> getSolicitationForEvaluation(
            @PathVariable String evaluationId,
            @PathVariable String solicitationId) {
        Map<String, Object> sol = solicitationClient.getSolicitation(solicitationId);
        return ResponseEntity.ok(sol);
    }

    /** Create a new evaluation panel. ⚠ Item 3 — no idempotency key. */
    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@RequestBody Map<String, Object> req) {
        Map<String, Object> resp = new HashMap<>();
        resp.put("evaluationId", UUID.randomUUID().toString());
        resp.put("solicitationId", req.get("solicitationId"));
        resp.put("status", "OPEN");
        return ResponseEntity.ok(resp);
    }
}
