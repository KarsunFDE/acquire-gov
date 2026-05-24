package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.ContractModification;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface ContractModificationRepository extends MongoRepository<ContractModification, String> {
    List<ContractModification> findByContractIdOrderByModNumberAsc(String contractId);
}
