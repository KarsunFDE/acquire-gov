package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.Amendment;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface AmendmentRepository extends MongoRepository<Amendment, String> {

    List<Amendment> findBySolicitationIdOrderByNumberAsc(String solicitationId);

    /** ⚠ Item 10 — declared but unused. */
    List<Amendment> findByAgencyId(String agencyId);
}
