package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/** Per-evaluator, per-proposal, per-factor score. FAR 15.305. */
@Document(collection = "evaluation_scores")
public class EvaluationScore {

    @Id
    private String id;

    private String evaluationId;
    private String evaluatorId;
    private String proposalId;
    private String factorId;
    private int score;       // raw 0-100 or factor-defined scale
    private String narrative;
    private Instant scoredAt;

    public EvaluationScore() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getEvaluationId() { return evaluationId; }
    public void setEvaluationId(String evaluationId) { this.evaluationId = evaluationId; }
    public String getEvaluatorId() { return evaluatorId; }
    public void setEvaluatorId(String evaluatorId) { this.evaluatorId = evaluatorId; }
    public String getProposalId() { return proposalId; }
    public void setProposalId(String proposalId) { this.proposalId = proposalId; }
    public String getFactorId() { return factorId; }
    public void setFactorId(String factorId) { this.factorId = factorId; }
    public int getScore() { return score; }
    public void setScore(int score) { this.score = score; }
    public String getNarrative() { return narrative; }
    public void setNarrative(String narrative) { this.narrative = narrative; }
    public Instant getScoredAt() { return scoredAt; }
    public void setScoredAt(Instant scoredAt) { this.scoredAt = scoredAt; }
}
