package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/** CDRL-tracked deliverable. */
@Document(collection = "deliverables")
public class Deliverable {

    @Id
    private String id;

    private String contractId;
    private String agencyId;
    private String cdrlNumber;
    private String title;
    private Instant dueAt;
    private String status; // PENDING / SUBMITTED / ACCEPTED / REJECTED
    private String acceptedBy;
    private Instant acceptedAt;

    public Deliverable() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getContractId() { return contractId; }
    public void setContractId(String contractId) { this.contractId = contractId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getCdrlNumber() { return cdrlNumber; }
    public void setCdrlNumber(String cdrlNumber) { this.cdrlNumber = cdrlNumber; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public Instant getDueAt() { return dueAt; }
    public void setDueAt(Instant dueAt) { this.dueAt = dueAt; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getAcceptedBy() { return acceptedBy; }
    public void setAcceptedBy(String acceptedBy) { this.acceptedBy = acceptedBy; }
    public Instant getAcceptedAt() { return acceptedAt; }
    public void setAcceptedAt(Instant acceptedAt) { this.acceptedAt = acceptedAt; }
}
