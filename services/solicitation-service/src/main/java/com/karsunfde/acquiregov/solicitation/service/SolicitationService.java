package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.audit.AuditLogger;
import com.karsunfde.acquiregov.solicitation.dto.SolicitationCreateRequest;
import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import com.karsunfde.acquiregov.solicitation.repository.SolicitationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Solicitation business logic.
 *
 * Brownfield-debt items present in this class:
 *   - Item 2 — {@link AuditLogger#recordAsync} runs after response flushes.
 *   - Item 9 — description is stored verbatim (no Jsoup.clean).
 *   - Item 10 — listAll calls repo.findAll() not findByAgencyId.
 */
@Service
public class SolicitationService {

    private static final Logger log = LoggerFactory.getLogger(SolicitationService.class);

    private final SolicitationRepository repo;
    private final AuditLogger auditLogger;

    @Autowired
    public SolicitationService(SolicitationRepository repo, AuditLogger auditLogger) {
        this.repo = repo;
        this.auditLogger = auditLogger;
    }

    public Solicitation create(SolicitationCreateRequest req, String actor) {
        Solicitation s = new Solicitation();
        s.setAgencyId(req.getAgencyId());
        s.setTitle(req.getTitle());
        // ⚠ Item 9 — no Jsoup.clean, no escape, no length cap.
        s.setDescription(req.getDescription());
        s.setStatus(req.getStatus() != null ? req.getStatus() : "DRAFT");
        s.setCreatedAt(Instant.now());
        s.setUpdatedAt(Instant.now());

        Solicitation saved = repo.save(s);

        // ⚠ Item 2 — fire-and-forget. Returns immediately, controller flushes
        //   response, audit may or may not land.
        auditLogger.recordAsync("CREATE", "solicitation", saved.getId(),
            actor, saved.getAgencyId());

        log.info("solicitation created id={} agencyId={} correlationId=N/A",
            saved.getId(), saved.getAgencyId());

        return saved;
    }

    public Optional<Solicitation> findById(String id) {
        return repo.findById(id);
    }

    /**
     * ⚠ Item 10 — returns solicitations across ALL agencies. The
     * {@code findByAgencyId} method exists on the repository but isn't
     * called from anywhere.
     */
    public List<Solicitation> listAll() {
        return repo.findAll();
    }

    public Optional<Solicitation> update(String id, SolicitationCreateRequest req, String actor) {
        return repo.findById(id).map(s -> {
            s.setTitle(req.getTitle());
            // ⚠ Item 9.
            s.setDescription(req.getDescription());
            if (req.getStatus() != null) s.setStatus(req.getStatus());
            s.setUpdatedAt(Instant.now());
            Solicitation saved = repo.save(s);
            auditLogger.recordAsync("UPDATE", "solicitation", saved.getId(),
                actor, saved.getAgencyId());
            return saved;
        });
    }

    public boolean delete(String id, String actor) {
        return repo.findById(id).map(s -> {
            repo.deleteById(id);
            auditLogger.recordAsync("DELETE", "solicitation", id, actor, s.getAgencyId());
            return true;
        }).orElse(false);
    }
}
