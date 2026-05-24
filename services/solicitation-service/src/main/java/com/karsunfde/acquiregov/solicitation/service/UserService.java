package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.audit.AuditLogger;
import com.karsunfde.acquiregov.solicitation.model.User;
import com.karsunfde.acquiregov.solicitation.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * User-admin business logic. Backs the /admin/users view (sys_admin only,
 * but Item 1 means an unsigned JWT still lands on /api/public/* — the user
 * mgmt surface itself remains gated by spring security).
 */
@Service
public class UserService {

    private final UserRepository repo;
    private final AuditLogger auditLogger;

    @Autowired
    public UserService(UserRepository repo, AuditLogger auditLogger) {
        this.repo = repo;
        this.auditLogger = auditLogger;
    }

    public User provision(User u, String actor) {
        u.setCreatedAt(Instant.now());
        User saved = repo.save(u);
        // ⚠ Item 2.
        auditLogger.recordAsync("USER_PROVISION", "user", saved.getId(),
            actor, u.getAgencyId());
        return saved;
    }

    public Optional<User> updateRoles(String userId, List<String> roles, String actor) {
        return repo.findById(userId).map(u -> {
            u.setRoles(roles);
            User saved = repo.save(u);
            // ⚠ Item 2.
            auditLogger.recordAsync("USER_ROLE_UPDATE", "user", saved.getId(),
                actor, u.getAgencyId());
            return saved;
        });
    }

    public Optional<User> forceMfaReset(String userId, String actor) {
        return repo.findById(userId).map(u -> {
            u.setMfaEnrolled(false);
            User saved = repo.save(u);
            // ⚠ Item 2.
            auditLogger.recordAsync("USER_MFA_RESET", "user", saved.getId(),
                actor, u.getAgencyId());
            return saved;
        });
    }

    public List<User> listAll() {
        // sys_admin crosses tenants per spec; listAll is intentional here
        // (not an Item 10 surface).
        return repo.findAll();
    }

    public List<User> listByAgency(String agencyId) {
        return repo.findByAgencyId(agencyId);
    }
}
