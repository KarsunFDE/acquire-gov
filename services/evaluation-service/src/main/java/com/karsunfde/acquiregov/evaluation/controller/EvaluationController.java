package com.karsunfde.acquiregov.evaluation.controller;

import com.karsunfde.acquiregov.evaluation.client.SolicitationClient;
import com.karsunfde.acquiregov.evaluation.model.Evaluation;
import com.karsunfde.acquiregov.evaluation.model.EvaluationScore;
import com.karsunfde.acquiregov.evaluation.service.EvaluationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Evaluation panel REST surface — Workflow 4 (eval → consensus → SSDD).
 *
 * Endpoints (feature-inventory-target.md, evaluation-service rows):
 *   POST   /api/evaluations
 *   GET    /api/evaluations/{id}
 *   POST   /api/evaluations/{id}/panel
 *   POST   /api/evaluations/{id}/scores
 *   GET    /api/evaluations/{id}/consensus
 *   POST   /api/evaluations/{id}/ssdd
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
    private final EvaluationService svc;

    @Autowired
    public EvaluationController(SolicitationClient solicitationClient, EvaluationService svc) {
        this.solicitationClient = solicitationClient;
        this.svc = svc;
    }

    /** Fetch the solicitation snapshot the evaluation panel is reviewing. */
    @GetMapping("/{evaluationId}/solicitation/{solicitationId}")
    public ResponseEntity<Map<String, Object>> getSolicitationForEvaluation(
            @PathVariable String evaluationId,
            @PathVariable String solicitationId) {
        // ⚠ Item 3 — no circuit breaker on this hop.
        Map<String, Object> sol = solicitationClient.getSolicitation(solicitationId);
        return ResponseEntity.ok(sol);
    }

    /** Create a new evaluation panel. ⚠ Item 3 — no idempotency key. */
    @PostMapping
    public ResponseEntity<Evaluation> create(@RequestBody Map<String, Object> req,
                                              @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        String solicitationId = String.valueOf(req.get("solicitationId"));
        String agencyId = (String) req.getOrDefault("agencyId", "GSA-FAS");
        return ResponseEntity.ok(svc.create(solicitationId, agencyId, actor));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Evaluation> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/panel")
    public ResponseEntity<Evaluation> assignPanel(
            @PathVariable String id,
            @RequestBody Map<String, List<String>> body,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.assignPanel(id, body.getOrDefault("panelMembers", List.of()), actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/scores")
    public ResponseEntity<EvaluationScore> submitScore(
            @PathVariable String id,
            @RequestBody EvaluationScore score,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.submitScore(id, score, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/consensus")
    public Map<String, Map<String, Double>> consensus(@PathVariable String id) {
        return svc.consensus(id);
    }

    @PostMapping("/{id}/ssdd")
    public ResponseEntity<Map<String, Object>> ssdd(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.draftSsdd(id, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
