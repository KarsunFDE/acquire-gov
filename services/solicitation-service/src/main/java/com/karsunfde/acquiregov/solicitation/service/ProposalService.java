package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.audit.AuditLogger;
import com.karsunfde.acquiregov.solicitation.dto.ProposalSubmitRequest;
import com.karsunfde.acquiregov.solicitation.model.Proposal;
import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import com.karsunfde.acquiregov.solicitation.repository.ProposalRepository;
import com.karsunfde.acquiregov.solicitation.repository.SolicitationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Proposal intake + sealed-lockbox workflow (Workflow 3).
 *
 * Brownfield-debt items present here:
 *   - Item 2 — unseal is multi-step; race with crash can leave the unseal
 *     event un-audited.
 *   - Item 10 — list endpoints do not enforce per-vendor agency boundary.
 */
@Service
public class ProposalService {

    private static final Logger log = LoggerFactory.getLogger(ProposalService.class);

    private final ProposalRepository repo;
    private final SolicitationRepository solRepo;
    private final AuditLogger auditLogger;

    @Autowired
    public ProposalService(ProposalRepository repo,
                           SolicitationRepository solRepo,
                           AuditLogger auditLogger) {
        this.repo = repo;
        this.solRepo = solRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Proposal> submit(String solicitationId, ProposalSubmitRequest req, String actor) {
        Optional<Solicitation> solOpt = solRepo.findById(solicitationId);
        if (solOpt.isEmpty()) return Optional.empty();
        Solicitation sol = solOpt.get();

        Proposal p = new Proposal();
        p.setSolicitationId(solicitationId);
        p.setAgencyId(sol.getAgencyId());
        p.setVendorId(req.getVendorId());
        p.setVolumes(req.getVolumes());
        p.setAcknowledgedAmendments(req.getAcknowledgedAmendments());
        p.setStatus("SEALED");
        p.setSubmittedAt(Instant.now());
        p.setSealedUntil(sol.getClosingAt());
        Proposal saved = repo.save(p);

        // ⚠ Item 2.
        auditLogger.recordAsync("PROPOSAL_SUBMIT", "proposal", saved.getId(),
            actor, sol.getAgencyId());

        log.info("proposal submitted solicitationId={} vendorId={}",
            solicitationId, req.getVendorId());
        return Optional.of(saved);
    }

    /**
     * Vendor-side endpoint to acknowledge an amendment for a proposal-in-progress
     * (FAR 15.206 — vendors must re-acknowledge after scope-changing amendments).
     */
    public Optional<Proposal> acknowledgeAmendment(String proposalId, int amendmentNumber, String actor) {
        return repo.findById(proposalId).map(p -> {
            if (!p.getAcknowledgedAmendments().contains(amendmentNumber)) {
                p.getAcknowledgedAmendments().add(amendmentNumber);
            }
            Proposal saved = repo.save(p);
            // ⚠ Item 2.
            auditLogger.recordAsync("PROPOSAL_ACK_AMEND", "proposal",
                saved.getId(), actor, p.getAgencyId());
            return saved;
        });
    }

    public List<Proposal> listForSolicitation(String solicitationId) {
        // ⚠ Item 10 — should re-check the caller's agency.
        return repo.findBySolicitationId(solicitationId);
    }

    public List<Proposal> listForVendor(String vendorId) {
        return repo.findByVendorId(vendorId);
    }
}
