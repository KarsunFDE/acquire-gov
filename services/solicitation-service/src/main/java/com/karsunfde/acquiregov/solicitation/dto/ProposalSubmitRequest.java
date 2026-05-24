package com.karsunfde.acquiregov.solicitation.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * Vendor proposal-submission DTO. Volumes are GridFS object IDs (uploaded
 * separately via the multipart form endpoint — stubbed for now).
 */
public class ProposalSubmitRequest {
    private String vendorId;
    private List<String> volumes = new ArrayList<>();
    /** Numbers of amendments this proposal acknowledges at submit time. */
    private List<Integer> acknowledgedAmendments = new ArrayList<>();

    public ProposalSubmitRequest() {}

    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
    public List<String> getVolumes() { return volumes; }
    public void setVolumes(List<String> volumes) { this.volumes = volumes; }
    public List<Integer> getAcknowledgedAmendments() { return acknowledgedAmendments; }
    public void setAcknowledgedAmendments(List<Integer> acknowledgedAmendments) { this.acknowledgedAmendments = acknowledgedAmendments; }
}
