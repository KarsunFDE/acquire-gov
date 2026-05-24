package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.Contract;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface ContractRepository extends MongoRepository<Contract, String> {
    Optional<Contract> findByAwardId(String awardId);
    /** ⚠ Item 10. */
    List<Contract> findByAgencyId(String agencyId);
    List<Contract> findByVendorId(String vendorId);
}
