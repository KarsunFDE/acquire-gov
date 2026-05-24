package com.karsunfde.acquiregov.evaluation.controller;

import com.karsunfde.acquiregov.evaluation.model.Award;
import com.karsunfde.acquiregov.evaluation.model.DebriefRequest;
import com.karsunfde.acquiregov.evaluation.service.AwardService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class AwardController {

    private final AwardService svc;

    @Autowired
    public AwardController(AwardService svc) {
        this.svc = svc;
    }

    @PostMapping("/evaluations/{id}/award")
    public ResponseEntity<Award> recordAward(
            @PathVariable("id") String evaluationId,
            @RequestBody Map<String, String> body,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        String winningProposalId = body.getOrDefault("winningProposalId", null);
        return svc.recordAward(evaluationId, winningProposalId, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/awards/{id}")
    public ResponseEntity<Award> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/awards/{id}/debrief-request")
    public ResponseEntity<DebriefRequest> requestDebrief(
            @PathVariable("id") String awardId,
            @RequestBody Map<String, String> body,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        // ⚠ Item 9 — body.narrative passed straight through.
        return svc.requestDebrief(awardId,
                body.get("vendorId"),
                body.getOrDefault("narrative", ""),
                actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
