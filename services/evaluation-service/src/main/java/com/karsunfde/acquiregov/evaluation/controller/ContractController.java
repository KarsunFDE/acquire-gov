package com.karsunfde.acquiregov.evaluation.controller;

import com.karsunfde.acquiregov.evaluation.model.*;
import com.karsunfde.acquiregov.evaluation.service.ContractService;
import com.karsunfde.acquiregov.evaluation.service.CparService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/contracts")
public class ContractController {

    private final ContractService svc;
    private final CparService cparSvc;

    @Autowired
    public ContractController(ContractService svc, CparService cparSvc) {
        this.svc = svc;
        this.cparSvc = cparSvc;
    }

    @GetMapping("/{id}")
    public ResponseEntity<Contract> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<Contract> create(@RequestBody Contract c,
                                            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return ResponseEntity.ok(svc.create(c, actor));
    }

    @PostMapping("/{id}/modifications")
    public ResponseEntity<ContractModification> issueMod(
            @PathVariable String id,
            @RequestBody ContractModification mod,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.issueMod(id, mod, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/deliverables")
    public List<Deliverable> listDeliverables(@PathVariable String id) {
        // ⚠ Item 3 reinforcement.
        return svc.listDeliverables(id);
    }

    @PostMapping("/{id}/qasp-findings")
    public ResponseEntity<QaspFinding> recordQasp(
            @PathVariable String id,
            @RequestBody QaspFinding finding,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.recordQaspFinding(id, finding, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/cpars")
    public ResponseEntity<Cpar> openCpar(
            @PathVariable String id,
            @RequestBody Cpar cpar,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return cparSvc.openCpar(id, cpar, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/cpars/{cparId}/rebuttal")
    public ResponseEntity<Cpar> recordRebuttal(
            @PathVariable String id,
            @PathVariable String cparId,
            @RequestBody Map<String, String> body,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return cparSvc.recordRebuttal(cparId, body.getOrDefault("rebuttal", ""), actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/cpars/{cparId}/finalize")
    public ResponseEntity<Cpar> finalizeCpar(
            @PathVariable String id,
            @PathVariable String cparId,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return cparSvc.finalizeCpar(cparId, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
