package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.Award;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface AwardRepository extends MongoRepository<Award, String> {
    Optional<Award> findByEvaluationId(String evaluationId);
    /** ⚠ Item 10 — declared but unused. */
    List<Award> findByAgencyId(String agencyId);
}
