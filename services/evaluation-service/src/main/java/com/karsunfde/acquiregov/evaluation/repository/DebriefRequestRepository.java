package com.karsunfde.acquiregov.evaluation.repository;

import com.karsunfde.acquiregov.evaluation.model.DebriefRequest;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface DebriefRequestRepository extends MongoRepository<DebriefRequest, String> {
    List<DebriefRequest> findByAwardId(String awardId);
}
