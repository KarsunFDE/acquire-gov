package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/** Contract modification. Workflow 5. */
@Document(collection = "contract_modifications")
public class ContractModification {

    @Id
    private String id;

    private String contractId;
    private String agencyId;
    private int modNumber;
    private String type; // BILATERAL / UNILATERAL
    private String summary;
    private Instant effectiveAt;
    private Instant createdAt;

    public ContractModification() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getContractId() { return contractId; }
    public void setContractId(String contractId) { this.contractId = contractId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public int getModNumber() { return modNumber; }
    public void setModNumber(int modNumber) { this.modNumber = modNumber; }
    public String getType() { return type; }
    public void setType(String type) { this.type = type; }
    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }
    public Instant getEffectiveAt() { return effectiveAt; }
    public void setEffectiveAt(Instant effectiveAt) { this.effectiveAt = effectiveAt; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
