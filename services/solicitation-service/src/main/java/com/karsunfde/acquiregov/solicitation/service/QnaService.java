package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.audit.AuditLogger;
import com.karsunfde.acquiregov.solicitation.dto.QnaAnswerRequest;
import com.karsunfde.acquiregov.solicitation.dto.QnaRequest;
import com.karsunfde.acquiregov.solicitation.model.Qna;
import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import com.karsunfde.acquiregov.solicitation.repository.QnaRepository;
import com.karsunfde.acquiregov.solicitation.repository.SolicitationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Vendor Q&A workflow.
 *
 * Brownfield-debt items present here:
 *   - Item 2 — Q&A state transitions audit-logged via recordAsync.
 *   - Item 9 — question + answer stored verbatim; both feed the
 *     ai-orchestrator /answer-qa prompt.
 *   - Item 10 — listForSolicitation does not re-check agency.
 */
@Service
public class QnaService {

    private static final Logger log = LoggerFactory.getLogger(QnaService.class);

    private final QnaRepository repo;
    private final SolicitationRepository solRepo;
    private final AuditLogger auditLogger;

    @Autowired
    public QnaService(QnaRepository repo, SolicitationRepository solRepo, AuditLogger auditLogger) {
        this.repo = repo;
        this.solRepo = solRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Qna> submit(String solicitationId, QnaRequest req, String actor) {
        Optional<Solicitation> solOpt = solRepo.findById(solicitationId);
        if (solOpt.isEmpty()) return Optional.empty();
        Solicitation sol = solOpt.get();

        Qna q = new Qna();
        q.setSolicitationId(solicitationId);
        q.setAgencyId(sol.getAgencyId());
        // ⚠ Item 9 — raw HTML accepted.
        q.setQuestion(req.getQuestion());
        q.setVendorId(req.getVendorId());
        q.setStatus("SUBMITTED");
        q.setSubmittedAt(Instant.now());
        Qna saved = repo.save(q);

        // ⚠ Item 2 — fire-and-forget.
        auditLogger.recordAsync("QNA_SUBMIT", "qna", saved.getId(), actor, sol.getAgencyId());

        log.info("qna submitted solicitationId={} vendorId={}", solicitationId, req.getVendorId());
        return Optional.of(saved);
    }

    public Optional<Qna> answer(String qnaId, QnaAnswerRequest req, String actor) {
        return repo.findById(qnaId).map(q -> {
            // ⚠ Item 9.
            q.setAnswer(req.getAnswer());
            q.setStatus("PUBLISHED");
            q.setAnsweredAt(Instant.now());
            Qna saved = repo.save(q);
            // ⚠ Item 2.
            auditLogger.recordAsync("QNA_ANSWER", "qna", saved.getId(), actor, q.getAgencyId());
            return saved;
        });
    }

    public List<Qna> listForSolicitation(String solicitationId) {
        // ⚠ Item 10 — does not re-check caller agency.
        return repo.findBySolicitationId(solicitationId);
    }
}
