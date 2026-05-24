package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.Deliverable;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface DeliverableRepository extends MongoRepository<Deliverable, String> {
    List<Deliverable> findByContractId(String contractId);
}
