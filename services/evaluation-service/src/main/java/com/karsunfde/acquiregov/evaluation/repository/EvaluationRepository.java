package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.Evaluation;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface EvaluationRepository extends MongoRepository<Evaluation, String> {
    List<Evaluation> findBySolicitationId(String solicitationId);
    /** ⚠ Item 10 — declared but list endpoints often skip. */
    List<Evaluation> findByAgencyId(String agencyId);
}
