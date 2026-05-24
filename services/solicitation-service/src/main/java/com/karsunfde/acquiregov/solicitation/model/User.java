package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * User identity record. {@code sub} = OIDC subject claim, joins to JWT.
 * Roles + agencyId resolved here, not from JWT (defense-in-depth — though
 * Item 1 currently makes the JWT untrusted on /api/public/* anyway).
 */
@Document(collection = "users")
public class User {

    @Id
    private String id;

    private String sub;
    private String email;
    private List<String> roles = new ArrayList<>();
    private String agencyId;
    private boolean mfaEnrolled;
    private Instant lastLogin;
    private Instant createdAt;

    public User() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getSub() { return sub; }
    public void setSub(String sub) { this.sub = sub; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public List<String> getRoles() { return roles; }
    public void setRoles(List<String> roles) { this.roles = roles; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public boolean isMfaEnrolled() { return mfaEnrolled; }
    public void setMfaEnrolled(boolean mfaEnrolled) { this.mfaEnrolled = mfaEnrolled; }
    public Instant getLastLogin() { return lastLogin; }
    public void setLastLogin(Instant lastLogin) { this.lastLogin = lastLogin; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
