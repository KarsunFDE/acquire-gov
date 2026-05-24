package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Vendor / contractor record.
 *
 * Identified by DUNS (legacy) or UEI (SAM.gov-current). Multi-tenant via
 * {@code agencyVisibility} — vendor can be visible to many agencies (per
 * SAM.gov registration model).
 *
 * ⚠ Item 10 reinforcement — {@code agencyVisibility} list exists but list
 * endpoints don't filter on it (see {@link com.karsunfde.acquiregov.solicitation.repository.VendorRepository}).
 */
@Document(collection = "vendors")
public class Vendor {

    @Id
    private String id;

    private String duns;
    private String uei;
    private String cage;
    private String name;

    /** Agencies this vendor is registered to do business with. */
    private List<String> agencyVisibility = new ArrayList<>();

    private List<String> naicsCodes = new ArrayList<>();

    private Instant createdAt;

    public Vendor() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getDuns() { return duns; }
    public void setDuns(String duns) { this.duns = duns; }
    public String getUei() { return uei; }
    public void setUei(String uei) { this.uei = uei; }
    public String getCage() { return cage; }
    public void setCage(String cage) { this.cage = cage; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public List<String> getAgencyVisibility() { return agencyVisibility; }
    public void setAgencyVisibility(List<String> agencyVisibility) { this.agencyVisibility = agencyVisibility; }
    public List<String> getNaicsCodes() { return naicsCodes; }
    public void setNaicsCodes(List<String> naicsCodes) { this.naicsCodes = naicsCodes; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
