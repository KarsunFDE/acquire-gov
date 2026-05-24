package com.karsunfde.acquiregov.evaluation.service;

import com.karsunfde.acquiregov.evaluation.audit.EvalAuditLogger;
import com.karsunfde.acquiregov.evaluation.model.*;
import com.karsunfde.acquiregov.evaluation.repository.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Workflow 5 — contract administration (FAR Part 42).
 *
 * Brownfield-debt:
 *   - Item 2 — mod / deliverable / QASP transitions audit-logged async.
 *   - Item 3 — deliverables list calls into the same RestTemplate path that
 *     reaches solicitation-service (cohort exercises this in W4 Thu).
 */
@Service
public class ContractService {

    private final ContractRepository contractRepo;
    private final ContractModificationRepository modRepo;
    private final DeliverableRepository deliverableRepo;
    private final QaspFindingRepository qaspRepo;
    private final EvalAuditLogger auditLogger;

    @Autowired
    public ContractService(ContractRepository contractRepo,
                           ContractModificationRepository modRepo,
                           DeliverableRepository deliverableRepo,
                           QaspFindingRepository qaspRepo,
                           EvalAuditLogger auditLogger) {
        this.contractRepo = contractRepo;
        this.modRepo = modRepo;
        this.deliverableRepo = deliverableRepo;
        this.qaspRepo = qaspRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Contract> findById(String id) { return contractRepo.findById(id); }

    public Contract create(Contract c, String actor) {
        if (c.getState() == null) c.setState("ACTIVE");
        Contract saved = contractRepo.save(c);
        auditLogger.recordAsync("CONTRACT_CREATE", "contract", saved.getId(),
            actor, c.getAgencyId());
        return saved;
    }

    public Optional<ContractModification> issueMod(String contractId, ContractModification mod, String actor) {
        return contractRepo.findById(contractId).map(c -> {
            List<ContractModification> existing = modRepo.findByContractIdOrderByModNumberAsc(contractId);
            int next = existing.isEmpty() ? 1 : existing.get(existing.size() - 1).getModNumber() + 1;
            mod.setContractId(contractId);
            mod.setAgencyId(c.getAgencyId());
            mod.setModNumber(next);
            mod.setCreatedAt(Instant.now());
            if (mod.getEffectiveAt() == null) mod.setEffectiveAt(Instant.now());
            ContractModification saved = modRepo.save(mod);
            // ⚠ Item 2.
            auditLogger.recordAsync("CONTRACT_MOD", "modification", saved.getId(),
                actor, c.getAgencyId());
            return saved;
        });
    }

    public List<Deliverable> listDeliverables(String contractId) {
        // ⚠ Item 3 reinforcement — caller often joins with solicitation-service
        // to render context; the join path goes through the no-circuit-breaker
        // SolicitationClient.
        return deliverableRepo.findByContractId(contractId);
    }

    public Optional<QaspFinding> recordQaspFinding(String contractId, QaspFinding finding, String actor) {
        return contractRepo.findById(contractId).map(c -> {
            finding.setContractId(contractId);
            finding.setAgencyId(c.getAgencyId());
            finding.setStatus(finding.getStatus() == null ? "OPEN" : finding.getStatus());
            finding.setCreatedAt(Instant.now());
            QaspFinding saved = qaspRepo.save(finding);
            // ⚠ Item 2.
            auditLogger.recordAsync("QASP_FINDING", "qasp", saved.getId(),
                actor, c.getAgencyId());
            return saved;
        });
    }
}
