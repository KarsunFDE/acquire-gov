package com.karsunfde.acquiregov.solicitation.controller;

import com.karsunfde.acquiregov.solicitation.model.Proposal;
import com.karsunfde.acquiregov.solicitation.model.Vendor;
import com.karsunfde.acquiregov.solicitation.service.ProposalService;
import com.karsunfde.acquiregov.solicitation.service.VendorService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Vendor registry endpoints + vendor-self proposal portal listing.
 *
 * ⚠ Item 10 — /api/vendors (listAll) leaks across agencies.
 */
@RestController
@RequestMapping("/api/vendors")
public class VendorController {

    private final VendorService svc;
    private final ProposalService proposalSvc;

    @Autowired
    public VendorController(VendorService svc, ProposalService proposalSvc) {
        this.svc = svc;
        this.proposalSvc = proposalSvc;
    }

    @GetMapping
    public List<Vendor> list() {
        // ⚠ Item 10.
        return svc.listAll();
    }

    @PostMapping
    public ResponseEntity<Vendor> register(@RequestBody Vendor v,
                                            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return ResponseEntity.ok(svc.register(v, actor));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Vendor> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    /** Vendor self-portal — list of MY proposals across all opportunities. */
    @GetMapping("/{id}/proposals")
    public List<Proposal> myProposals(@PathVariable String id) {
        // ⚠ Item 10 — relies on vendorId match alone; no agency cross-check.
        return proposalSvc.listForVendor(id);
    }
}
