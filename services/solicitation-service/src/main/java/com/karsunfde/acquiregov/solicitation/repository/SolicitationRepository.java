package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

/**
 * ⚠ DELIBERATE — Item 10:
 *   {@code findAll()} returns solicitations across ALL agencies. There is a
 *   {@code findByAgencyId} method declared below — it just isn't called from
 *   {@code SolicitationService}. Cohort fixes in W2 Wed by switching all
 *   reads to {@code findByAgencyId} (and resolving agency from JWT).
 */
public interface SolicitationRepository extends MongoRepository<Solicitation, String> {

    /** Declared but not used — the cohort discovers and wires this up. */
    List<Solicitation> findByAgencyId(String agencyId);
}
