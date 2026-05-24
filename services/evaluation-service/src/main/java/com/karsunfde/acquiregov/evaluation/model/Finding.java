package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * OIG-style audit finding. Cohort's W6 runbook + ADR catalog + eval report
 * are modeled as Finding entities (the meta-mirror per feature-inventory-
 * target.md line 391).
 *
 * ⚠ Item 12 — first PR opens a finding against the repo itself (GHA lint
 * disabled).
 */
@Document(collection = "findings")
public class Finding {

    @Id
    private String id;

    private String openedBy;
    private String contractId;
    private String agencyId;
    private String findingType;
    private String severity;
    private String summary;
    private List<String> evidenceRequests = new ArrayList<>();
    private String remediationStatus; // OPEN / IN_PROGRESS / REMEDIATED / WAIVED
    private Instant dueAt;
    private Instant openedAt;
    private Instant closedAt;

    public Finding() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getOpenedBy() { return openedBy; }
    public void setOpenedBy(String openedBy) { this.openedBy = openedBy; }
    public String getContractId() { return contractId; }
    public void setContractId(String contractId) { this.contractId = contractId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getFindingType() { return findingType; }
    public void setFindingType(String findingType) { this.findingType = findingType; }
    public String getSeverity() { return severity; }
    public void setSeverity(String severity) { this.severity = severity; }
    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }
    public List<String> getEvidenceRequests() { return evidenceRequests; }
    public void setEvidenceRequests(List<String> evidenceRequests) { this.evidenceRequests = evidenceRequests; }
    public String getRemediationStatus() { return remediationStatus; }
    public void setRemediationStatus(String remediationStatus) { this.remediationStatus = remediationStatus; }
    public Instant getDueAt() { return dueAt; }
    public void setDueAt(Instant dueAt) { this.dueAt = dueAt; }
    public Instant getOpenedAt() { return openedAt; }
    public void setOpenedAt(Instant openedAt) { this.openedAt = openedAt; }
    public Instant getClosedAt() { return closedAt; }
    public void setClosedAt(Instant closedAt) { this.closedAt = closedAt; }
}
