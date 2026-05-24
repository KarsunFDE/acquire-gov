package com.karsunfde.acquiregov.evaluation.service;

import com.karsunfde.acquiregov.evaluation.audit.EvalAuditLogger;
import com.karsunfde.acquiregov.evaluation.model.Finding;
import com.karsunfde.acquiregov.evaluation.repository.FindingRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

/** OIG-style finding lifecycle. */
@Service
public class FindingService {

    private final FindingRepository repo;
    private final EvalAuditLogger auditLogger;

    @Autowired
    public FindingService(FindingRepository repo, EvalAuditLogger auditLogger) {
        this.repo = repo;
        this.auditLogger = auditLogger;
    }

    public Finding open(Finding f, String actor) {
        f.setOpenedAt(Instant.now());
        if (f.getRemediationStatus() == null) f.setRemediationStatus("OPEN");
        Finding saved = repo.save(f);
        // ⚠ Item 2.
        auditLogger.recordAsync("FINDING_OPEN", "finding", saved.getId(),
            actor, f.getAgencyId());
        return saved;
    }

    public List<Finding> list(String status) {
        return status != null ? repo.findByRemediationStatus(status) : repo.findAll();
    }

    public List<Finding> listForContract(String contractId) {
        return repo.findByContractId(contractId);
    }
}
