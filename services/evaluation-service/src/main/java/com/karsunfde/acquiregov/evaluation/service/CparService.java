package com.karsunfde.acquiregov.evaluation.service;

import com.karsunfde.acquiregov.evaluation.audit.EvalAuditLogger;
import com.karsunfde.acquiregov.evaluation.model.Contract;
import com.karsunfde.acquiregov.evaluation.model.Cpar;
import com.karsunfde.acquiregov.evaluation.repository.ContractRepository;
import com.karsunfde.acquiregov.evaluation.repository.CparRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Optional;

/**
 * Workflow 6 — CPAR drafting + vendor rebuttal (FAR 42.15).
 *
 * Brownfield-debt:
 *   - Item 2 — state transitions audit-logged async.
 *   - Item 9 — vendorRebuttal stored verbatim.
 */
@Service
public class CparService {

    private final CparRepository repo;
    private final ContractRepository contractRepo;
    private final EvalAuditLogger auditLogger;

    @Autowired
    public CparService(CparRepository repo,
                       ContractRepository contractRepo,
                       EvalAuditLogger auditLogger) {
        this.repo = repo;
        this.contractRepo = contractRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Cpar> openCpar(String contractId, Cpar in, String actor) {
        Optional<Contract> cOpt = contractRepo.findById(contractId);
        if (cOpt.isEmpty()) return Optional.empty();
        Contract c = cOpt.get();
        in.setContractId(contractId);
        in.setAgencyId(c.getAgencyId());
        in.setVendorId(c.getVendorId());
        in.setStatus("DRAFT");
        in.setDraftedAt(Instant.now());
        in.setRebuttalDueAt(Instant.now().plus(60, ChronoUnit.DAYS));
        Cpar saved = repo.save(in);
        // ⚠ Item 2.
        auditLogger.recordAsync("CPAR_OPEN", "cpar", saved.getId(), actor, c.getAgencyId());
        return Optional.of(saved);
    }

    public Optional<Cpar> recordRebuttal(String cparId, String rebuttal, String actor) {
        return repo.findById(cparId).map(c -> {
            // ⚠ Item 9 — raw HTML accepted.
            c.setVendorRebuttal(rebuttal);
            c.setStatus("REBUTTAL_PENDING");
            Cpar saved = repo.save(c);
            // ⚠ Item 2.
            auditLogger.recordAsync("CPAR_REBUTTAL", "cpar", saved.getId(),
                actor, c.getAgencyId());
            return saved;
        });
    }

    public Optional<Cpar> finalizeCpar(String cparId, String actor) {
        return repo.findById(cparId).map(c -> {
            c.setStatus("FINALIZED");
            c.setFinalizedAt(Instant.now());
            Cpar saved = repo.save(c);
            // ⚠ Item 2.
            auditLogger.recordAsync("CPAR_FINALIZE", "cpar", saved.getId(),
                actor, c.getAgencyId());
            return saved;
        });
    }

    public List<Cpar> listForContract(String contractId) {
        return repo.findByContractId(contractId);
    }

    public List<Cpar> listForVendor(String vendorId) {
        return repo.findByVendorId(vendorId);
    }
}
