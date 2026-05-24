package com.karsunfde.acquiregov.evaluation.controller;

import com.karsunfde.acquiregov.evaluation.model.Finding;
import com.karsunfde.acquiregov.evaluation.service.FindingService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * OIG-style findings tracker. Backs the /admin/findings view.
 *
 * ⚠ Item 12 reinforcement — first PR opens a finding against the repo's own
 * CI (meta-mirror).
 */
@RestController
@RequestMapping("/api/findings")
public class FindingController {

    private final FindingService svc;

    @Autowired
    public FindingController(FindingService svc) {
        this.svc = svc;
    }

    @GetMapping
    public List<Finding> list(@RequestParam(required = false) String status) {
        return svc.list(status);
    }

    @PostMapping
    public Finding open(@RequestBody Finding f,
                         @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.open(f, actor);
    }

    @GetMapping("/contract/{contractId}")
    public List<Finding> forContract(@PathVariable String contractId) {
        return svc.listForContract(contractId);
    }
}
