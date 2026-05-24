package com.karsunfde.acquiregov.solicitation.controller;

import com.karsunfde.acquiregov.solicitation.model.User;
import com.karsunfde.acquiregov.solicitation.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * /admin/users backend — provisioning + role assignment + MFA reset.
 *
 * sys_admin scope (cross-agency). Item 1's JWT-skip on /api/public/* means
 * an attacker who mints an unsigned JWT and brushes against /api/public/**
 * doesn't directly land here, but Item 1's downstream-trust convention
 * still bleeds into ops trust assumptions (W4 Wed OWASP LLM07/08 lesson).
 */
@RestController
@RequestMapping("/api/admin/users")
public class AdminUserController {

    private final UserService svc;

    @Autowired
    public AdminUserController(UserService svc) {
        this.svc = svc;
    }

    @GetMapping
    public List<User> list(@RequestParam(required = false) String agencyId) {
        return agencyId != null ? svc.listByAgency(agencyId) : svc.listAll();
    }

    @PostMapping
    public ResponseEntity<User> provision(@RequestBody User u,
                                           @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return ResponseEntity.ok(svc.provision(u, actor));
    }

    @PutMapping("/{userId}/roles")
    public ResponseEntity<User> updateRoles(@PathVariable String userId,
                                             @RequestBody Map<String, List<String>> body,
                                             @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        List<String> roles = body.getOrDefault("roles", List.of());
        return svc.updateRoles(userId, roles, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{userId}/mfa-reset")
    public ResponseEntity<User> mfaReset(@PathVariable String userId,
                                          @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.forceMfaReset(userId, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
