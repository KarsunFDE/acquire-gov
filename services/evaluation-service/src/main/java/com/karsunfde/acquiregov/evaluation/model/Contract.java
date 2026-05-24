package com.karsunfde.acquiregov.evaluation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.math.BigDecimal;

/** Awarded contract record. FAR Part 42 contract administration. */
@Document(collection = "contracts")
public class Contract {

    @Id
    private String id;

    private String awardId;
    private String agencyId;
    private String vendorId;
    private String contractNumber;
    private Instant periodOfPerformanceStart;
    private Instant periodOfPerformanceEnd;
    private BigDecimal ceilingValue;
    /** Parent IDIQ contract id if this is a task-order child. */
    private String idiqParentId;
    private String state; // ACTIVE / CLOSED / TERMINATED

    public Contract() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getAwardId() { return awardId; }
    public void setAwardId(String awardId) { this.awardId = awardId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
    public String getContractNumber() { return contractNumber; }
    public void setContractNumber(String contractNumber) { this.contractNumber = contractNumber; }
    public Instant getPeriodOfPerformanceStart() { return periodOfPerformanceStart; }
    public void setPeriodOfPerformanceStart(Instant periodOfPerformanceStart) { this.periodOfPerformanceStart = periodOfPerformanceStart; }
    public Instant getPeriodOfPerformanceEnd() { return periodOfPerformanceEnd; }
    public void setPeriodOfPerformanceEnd(Instant periodOfPerformanceEnd) { this.periodOfPerformanceEnd = periodOfPerformanceEnd; }
    public BigDecimal getCeilingValue() { return ceilingValue; }
    public void setCeilingValue(BigDecimal ceilingValue) { this.ceilingValue = ceilingValue; }
    public String getIdiqParentId() { return idiqParentId; }
    public void setIdiqParentId(String idiqParentId) { this.idiqParentId = idiqParentId; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
}
