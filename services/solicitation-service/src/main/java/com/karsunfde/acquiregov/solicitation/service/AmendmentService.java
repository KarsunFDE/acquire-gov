package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.audit.AuditLogger;
import com.karsunfde.acquiregov.solicitation.dto.AmendmentRequest;
import com.karsunfde.acquiregov.solicitation.model.Amendment;
import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import com.karsunfde.acquiregov.solicitation.repository.AmendmentRepository;
import com.karsunfde.acquiregov.solicitation.repository.SolicitationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Amendment issuance (FAR 15.206). Workflow 2.
 *
 * Brownfield-debt items present here:
 *   - Item 2 — amendment publication writes are audit-logged via recordAsync.
 *   - Item 9 — changeSummary stored verbatim.
 *   - Item 10 — list endpoints call findBySolicitationId without re-checking
 *     the caller's agency claim against the solicitation's agency.
 */
@Service
public class AmendmentService {

    private static final Logger log = LoggerFactory.getLogger(AmendmentService.class);

    private final AmendmentRepository repo;
    private final SolicitationRepository solRepo;
    private final AuditLogger auditLogger;

    @Autowired
    public AmendmentService(AmendmentRepository repo,
                            SolicitationRepository solRepo,
                            AuditLogger auditLogger) {
        this.repo = repo;
        this.solRepo = solRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Amendment> issue(String solicitationId, AmendmentRequest req, String actor) {
        Optional<Solicitation> solOpt = solRepo.findById(solicitationId);
        if (solOpt.isEmpty()) return Optional.empty();
        Solicitation sol = solOpt.get();

        List<Amendment> existing = repo.findBySolicitationIdOrderByNumberAsc(solicitationId);
        int nextNumber = existing.isEmpty() ? 1 : existing.get(existing.size() - 1).getNumber() + 1;

        Amendment a = new Amendment();
        a.setSolicitationId(solicitationId);
        a.setAgencyId(sol.getAgencyId());
        a.setNumber(nextNumber);
        // ⚠ Item 9 — raw HTML stored.
        a.setChangeSummary(req.getChangeSummary());
        a.setRequiresAcknowledgement(req.isRequiresAcknowledgement());
        a.setEffectiveAt(req.getEffectiveAt() != null ? Instant.parse(req.getEffectiveAt()) : Instant.now());
        a.setCreatedAt(Instant.now());
        Amendment saved = repo.save(a);

        // ⚠ Item 2 — fire-and-forget.
        auditLogger.recordAsync("AMEND", "amendment", saved.getId(), actor, sol.getAgencyId());

        log.info("amendment issued solicitationId={} number={} agencyId={}",
            solicitationId, nextNumber, sol.getAgencyId());

        return Optional.of(saved);
    }

    public List<Amendment> listForSolicitation(String solicitationId) {
        // ⚠ Item 10 — does not re-check caller's agency claim.
        return repo.findBySolicitationIdOrderByNumberAsc(solicitationId);
    }
}
