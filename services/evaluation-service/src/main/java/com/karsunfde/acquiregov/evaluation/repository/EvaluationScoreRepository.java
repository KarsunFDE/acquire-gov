package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.EvaluationScore;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface EvaluationScoreRepository extends MongoRepository<EvaluationScore, String> {
    List<EvaluationScore> findByEvaluationId(String evaluationId);
    List<EvaluationScore> findByEvaluationIdAndProposalId(String evaluationId, String proposalId);
    List<EvaluationScore> findByEvaluatorId(String evaluatorId);
}
