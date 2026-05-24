package com.karsunfde.acquiregov.solicitation.controller;

import com.karsunfde.acquiregov.solicitation.dto.AmendmentRequest;
import com.karsunfde.acquiregov.solicitation.dto.ProposalSubmitRequest;
import com.karsunfde.acquiregov.solicitation.dto.QnaAnswerRequest;
import com.karsunfde.acquiregov.solicitation.dto.QnaRequest;
import com.karsunfde.acquiregov.solicitation.dto.SolicitationCreateRequest;
import com.karsunfde.acquiregov.solicitation.model.Amendment;
import com.karsunfde.acquiregov.solicitation.model.Proposal;
import com.karsunfde.acquiregov.solicitation.model.Qna;
import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import com.karsunfde.acquiregov.solicitation.service.AmendmentService;
import com.karsunfde.acquiregov.solicitation.service.ProposalService;
import com.karsunfde.acquiregov.solicitation.service.QnaService;
import com.karsunfde.acquiregov.solicitation.service.SolicitationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Solicitation REST surface — covers Workflow 1 (drafting → publication),
 * Workflow 2 (Q&A + amendments), Workflow 3 (proposal intake).
 *
 * Endpoints (feature-inventory-target.md, solicitation-service rows):
 *   POST    /api/solicitations
 *   GET     /api/solicitations
 *   GET     /api/solicitations/{id}
 *   PUT     /api/solicitations/{id}
 *   DELETE  /api/solicitations/{id}
 *   POST    /api/solicitations/{id}/publish
 *   POST    /api/solicitations/{id}/cancel
 *   POST    /api/solicitations/{id}/amendments
 *   GET     /api/solicitations/{id}/amendments
 *   POST    /api/solicitations/{id}/qa
 *   PUT     /api/solicitations/{id}/qa/{qnaId}/answer
 *   GET     /api/solicitations/{id}/qa
 *   POST    /api/solicitations/{id}/proposals
 *   GET     /api/solicitations/{id}/proposals
 *   POST    /api/solicitations/{id}/proposals/{pid}/acknowledge-amendment
 */
@RestController
@RequestMapping("/api/solicitations")
public class SolicitationController {

    private final SolicitationService svc;
    private final AmendmentService amendmentSvc;
    private final QnaService qnaSvc;
    private final ProposalService proposalSvc;

    @Autowired
    public SolicitationController(SolicitationService svc,
                                  AmendmentService amendmentSvc,
                                  QnaService qnaSvc,
                                  ProposalService proposalSvc) {
        this.svc = svc;
        this.amendmentSvc = amendmentSvc;
        this.qnaSvc = qnaSvc;
        this.proposalSvc = proposalSvc;
    }

    @GetMapping
    public List<Solicitation> list(@RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        // ⚠ Item 10 — does not filter by agency.
        return svc.listAll();
    }

    @GetMapping("/{id}")
    public ResponseEntity<Solicitation> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<Solicitation> create(
            @RequestBody SolicitationCreateRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        // ⚠ Item 9 — no validation on req.description.
        Solicitation created = svc.create(req, actor);
        return ResponseEntity.ok(created);
    }

    @PutMapping("/{id}")
    public ResponseEntity<Solicitation> update(
            @PathVariable String id,
            @RequestBody SolicitationCreateRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.update(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        boolean ok = svc.delete(id, actor);
        return ok ? ResponseEntity.noContent().build() : ResponseEntity.notFound().build();
    }

    // -------- State machine transitions (Workflow 1) --------

    @PostMapping("/{id}/publish")
    public ResponseEntity<Solicitation> publish(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.publish(id, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/cancel")
    public ResponseEntity<Solicitation> cancel(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.cancel(id, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // -------- Amendments (Workflow 2 — FAR 15.206) --------

    @PostMapping("/{id}/amendments")
    public ResponseEntity<Amendment> issueAmendment(
            @PathVariable String id,
            @RequestBody AmendmentRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return amendmentSvc.issue(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/amendments")
    public List<Amendment> listAmendments(@PathVariable String id) {
        // ⚠ Item 10 — does not re-check caller agency.
        return amendmentSvc.listForSolicitation(id);
    }

    // -------- Q&A (Workflow 2) --------

    @PostMapping("/{id}/qa")
    public ResponseEntity<Qna> submitQuestion(
            @PathVariable String id,
            @RequestBody QnaRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return qnaSvc.submit(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PutMapping("/{id}/qa/{qnaId}/answer")
    public ResponseEntity<Qna> answer(
            @PathVariable String id,
            @PathVariable String qnaId,
            @RequestBody QnaAnswerRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return qnaSvc.answer(qnaId, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/qa")
    public List<Qna> listQna(@PathVariable String id) {
        // ⚠ Item 10 — vendor should only see their own pre-publish entries.
        return qnaSvc.listForSolicitation(id);
    }

    // -------- Proposal intake (Workflow 3) --------

    @PostMapping("/{id}/proposals")
    public ResponseEntity<Proposal> submitProposal(
            @PathVariable String id,
            @RequestBody ProposalSubmitRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return proposalSvc.submit(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/proposals")
    public List<Proposal> listProposals(@PathVariable String id) {
        // ⚠ Item 2 — must be gated on post-deadline + audit-logged on view.
        // ⚠ Item 10 — does not re-check caller agency.
        return proposalSvc.listForSolicitation(id);
    }

    @PostMapping("/{id}/proposals/{pid}/acknowledge-amendment")
    public ResponseEntity<Proposal> acknowledgeAmendment(
            @PathVariable String id,
            @PathVariable("pid") String proposalId,
            @RequestParam("amendmentNumber") int amendmentNumber,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return proposalSvc.acknowledgeAmendment(proposalId, amendmentNumber, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
