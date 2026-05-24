package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.Finding;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface FindingRepository extends MongoRepository<Finding, String> {
    List<Finding> findByRemediationStatus(String status);
    List<Finding> findByContractId(String contractId);
}
