package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/** Quality Assurance Surveillance Plan finding. FAR Part 46. */
@Document(collection = "qasp_findings")
public class QaspFinding {

    @Id
    private String id;

    private String contractId;
    private String agencyId;
    private String findingText;
    private String severity; // LOW / MEDIUM / HIGH / CRITICAL
    private Instant remediationDue;
    private String status; // OPEN / REMEDIATED / WAIVED
    private Instant createdAt;

    public QaspFinding() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getContractId() { return contractId; }
    public void setContractId(String contractId) { this.contractId = contractId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getFindingText() { return findingText; }
    public void setFindingText(String findingText) { this.findingText = findingText; }
    public String getSeverity() { return severity; }
    public void setSeverity(String severity) { this.severity = severity; }
    public Instant getRemediationDue() { return remediationDue; }
    public void setRemediationDue(Instant remediationDue) { this.remediationDue = remediationDue; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
