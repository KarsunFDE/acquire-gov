package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.QaspFinding;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface QaspFindingRepository extends MongoRepository<QaspFinding, String> {
    List<QaspFinding> findByContractId(String contractId);
}
