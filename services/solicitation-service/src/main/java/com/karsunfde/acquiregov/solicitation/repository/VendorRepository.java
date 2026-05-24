package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.Vendor;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

/**
 * ⚠ Item 10 reinforcement — {@code findAll()} returns vendors across all
 * agencies. {@code findByAgencyVisibilityContains} exists for the W2 Wed fix
 * but isn't wired in.
 */
public interface VendorRepository extends MongoRepository<Vendor, String> {

    Optional<Vendor> findByDuns(String duns);

    Optional<Vendor> findByUei(String uei);

    /** Declared but not used — cohort wires this up W2 Wed. */
    List<Vendor> findByAgencyVisibilityContains(String agencyId);

    List<Vendor> findByNaicsCodesContains(String naics);
}
