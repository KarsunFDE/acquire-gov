package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.Qna;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface QnaRepository extends MongoRepository<Qna, String> {

    List<Qna> findBySolicitationId(String solicitationId);

    /** ⚠ Item 10 — declared but unused. */
    List<Qna> findByAgencyId(String agencyId);
}
