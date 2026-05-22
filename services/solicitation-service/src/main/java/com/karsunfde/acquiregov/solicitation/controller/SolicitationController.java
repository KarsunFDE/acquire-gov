package com.karsunfde.acquiregov.solicitation.controller;

import com.karsunfde.acquiregov.solicitation.dto.SolicitationCreateRequest;
import com.karsunfde.acquiregov.solicitation.model.Solicitation;
import com.karsunfde.acquiregov.solicitation.service.SolicitationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/solicitations")
public class SolicitationController {

    private final SolicitationService svc;

    @Autowired
    public SolicitationController(SolicitationService svc) {
        this.svc = svc;
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
}
