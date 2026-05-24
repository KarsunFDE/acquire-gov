package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.Proposal;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface ProposalRepository extends MongoRepository<Proposal, String> {

    List<Proposal> findBySolicitationId(String solicitationId);

    /** ⚠ Item 10 — vendors should NOT see other vendors' proposals; this
     *  method is the safe one but isn't always used. */
    List<Proposal> findByVendorId(String vendorId);

    /** ⚠ Item 10 — declared but unused. */
    List<Proposal> findByAgencyId(String agencyId);
}
