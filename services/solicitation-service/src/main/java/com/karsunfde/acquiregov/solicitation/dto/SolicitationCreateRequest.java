package com.karsunfde.acquiregov.solicitation.dto;

/**
 * Create-solicitation request DTO.
 *
 * ⚠ DELIBERATE — Item 9:
 *   No {@code @SafeHtml}, no {@code @NotBlank}, no length cap on
 *   {@code description}. The field accepts {@code <script>} tags verbatim.
 *   Cohort fixes in W4 Wed AI Security Engineering Day.
 *
 * ⚠ DELIBERATE — Item 10 reinforcement:
 *   {@code agencyId} is on the DTO but the controller doesn't cross-check it
 *   against the JWT's agency claim.
 */
public class SolicitationCreateRequest {

    private String agencyId;
    private String title;
    private String description; // ⚠ raw HTML accepted
    private String status;

    public SolicitationCreateRequest() {}

    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
