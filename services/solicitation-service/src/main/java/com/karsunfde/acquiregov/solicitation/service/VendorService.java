package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.audit.AuditLogger;
import com.karsunfde.acquiregov.solicitation.model.Vendor;
import com.karsunfde.acquiregov.solicitation.repository.VendorRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Vendor registry. Item 10 — listAll returns all vendors across agencies.
 */
@Service
public class VendorService {

    private final VendorRepository repo;
    private final AuditLogger auditLogger;

    @Autowired
    public VendorService(VendorRepository repo, AuditLogger auditLogger) {
        this.repo = repo;
        this.auditLogger = auditLogger;
    }

    public Vendor register(Vendor v, String actor) {
        v.setCreatedAt(Instant.now());
        Vendor saved = repo.save(v);
        // ⚠ Item 2.
        auditLogger.recordAsync("VENDOR_REGISTER", "vendor", saved.getId(),
            actor, "*");
        return saved;
    }

    public List<Vendor> listAll() {
        // ⚠ Item 10 — returns vendors across all agencies. Fixed surface
        // would call repo.findByAgencyVisibilityContains(jwt.agencyId).
        return repo.findAll();
    }

    public Optional<Vendor> findById(String id) { return repo.findById(id); }

    public Optional<Vendor> findByDuns(String duns) { return repo.findByDuns(duns); }

    public List<Vendor> findByNaics(String naics) {
        return repo.findByNaicsCodesContains(naics);
    }
}
