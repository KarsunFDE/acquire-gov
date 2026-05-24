package com.karsunfde.acquiregov.evaluation.service;

import com.karsunfde.acquiregov.evaluation.audit.EvalAuditLogger;
import com.karsunfde.acquiregov.evaluation.client.AiOrchestratorClient;
import com.karsunfde.acquiregov.evaluation.client.SolicitationClient;
import com.karsunfde.acquiregov.evaluation.model.Evaluation;
import com.karsunfde.acquiregov.evaluation.model.EvaluationScore;
import com.karsunfde.acquiregov.evaluation.repository.EvaluationRepository;
import com.karsunfde.acquiregov.evaluation.repository.EvaluationScoreRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Workflow 4 — evaluation → consensus → source selection → award (pre-award).
 *
 * Brownfield-debt items reinforced:
 *   - Item 3 — calls solicitation-service for each proposal text via
 *     SolicitationClient (no circuit breaker).
 *   - Item 2 — state transitions audit-logged via async.
 *   - Item 4 reinforcement — SSDD draft response from ai-orchestrator goes
 *     straight back; no structured-output schema enforcement.
 */
@Service
public class EvaluationService {

    private static final Logger log = LoggerFactory.getLogger(EvaluationService.class);

    private final EvaluationRepository evalRepo;
    private final EvaluationScoreRepository scoreRepo;
    private final SolicitationClient solicitationClient;
    private final AiOrchestratorClient aiClient;
    private final EvalAuditLogger auditLogger;

    @Autowired
    public EvaluationService(EvaluationRepository evalRepo,
                             EvaluationScoreRepository scoreRepo,
                             SolicitationClient solicitationClient,
                             AiOrchestratorClient aiClient,
                             EvalAuditLogger auditLogger) {
        this.evalRepo = evalRepo;
        this.scoreRepo = scoreRepo;
        this.solicitationClient = solicitationClient;
        this.aiClient = aiClient;
        this.auditLogger = auditLogger;
    }

    public Evaluation create(String solicitationId, String agencyId, String actor) {
        Evaluation e = new Evaluation();
        e.setSolicitationId(solicitationId);
        e.setAgencyId(agencyId);
        e.setState("OPEN");
        e.setCreatedAt(Instant.now());
        Evaluation saved = evalRepo.save(e);
        auditLogger.recordAsync("EVAL_CREATE", "evaluation", saved.getId(), actor, agencyId);
        return saved;
    }

    public Optional<Evaluation> findById(String id) {
        return evalRepo.findById(id);
    }

    public Optional<Evaluation> assignPanel(String evaluationId, List<String> panelMembers, String actor) {
        return evalRepo.findById(evaluationId).map(e -> {
            e.setPanelMembers(panelMembers);
            e.setState("PANEL_ASSIGNED");
            Evaluation saved = evalRepo.save(e);
            auditLogger.recordAsync("EVAL_PANEL_ASSIGN", "evaluation", saved.getId(),
                actor, e.getAgencyId());
            return saved;
        });
    }

    public Optional<EvaluationScore> submitScore(String evaluationId, EvaluationScore in, String actor) {
        Optional<Evaluation> eOpt = evalRepo.findById(evaluationId);
        if (eOpt.isEmpty()) return Optional.empty();
        Evaluation e = eOpt.get();

        // ⚠ Item 3 — fetches proposal context from solicitation-service for
        // each score submission. No circuit breaker; under TEP-week load
        // this is the thread-exhaustion reproducer.
        Map<String, Object> proposal = solicitationClient.getSolicitation(in.getProposalId());
        log.info("score submission evaluationId={} proposalId={} proposal-loaded={}",
            evaluationId, in.getProposalId(), proposal != null);

        in.setEvaluationId(evaluationId);
        in.setScoredAt(Instant.now());
        EvaluationScore saved = scoreRepo.save(in);

        // ⚠ Item 2.
        auditLogger.recordAsync("EVAL_SCORE", "score", saved.getId(),
            actor, e.getAgencyId());

        // Promote evaluation state on first score.
        if (!"SCORING".equals(e.getState())) {
            e.setState("SCORING");
            evalRepo.save(e);
        }
        return Optional.of(saved);
    }

    /** Aggregate panel consensus per proposal × factor. */
    public Map<String, Map<String, Double>> consensus(String evaluationId) {
        List<EvaluationScore> scores = scoreRepo.findByEvaluationId(evaluationId);
        Map<String, List<EvaluationScore>> byProposal = scores.stream()
            .collect(Collectors.groupingBy(EvaluationScore::getProposalId));
        Map<String, Map<String, Double>> out = new LinkedHashMap<>();
        for (Map.Entry<String, List<EvaluationScore>> p : byProposal.entrySet()) {
            Map<String, Double> byFactor = p.getValue().stream()
                .collect(Collectors.groupingBy(
                    EvaluationScore::getFactorId,
                    Collectors.averagingInt(EvaluationScore::getScore)));
            out.put(p.getKey(), byFactor);
        }
        return out;
    }

    /** Generate Source Selection Decision Document via ai-orchestrator. */
    public Optional<Map<String, Object>> draftSsdd(String evaluationId, String actor) {
        return evalRepo.findById(evaluationId).map(e -> {
            // ⚠ Item 4 reinforcement — raw response returned; no schema check.
            Map<String, Object> resp = aiClient.draftSsdd(evaluationId);
            e.setState("CONSENSUS");
            e.setConsensusAt(Instant.now());
            // Store doc id placeholder from response if present.
            if (resp != null && resp.get("clause_id") != null) {
                e.setSsddDocId(resp.get("clause_id").toString());
            }
            evalRepo.save(e);
            auditLogger.recordAsync("SSDD_DRAFT", "evaluation", evaluationId,
                actor, e.getAgencyId());
            return resp;
        });
    }
}
