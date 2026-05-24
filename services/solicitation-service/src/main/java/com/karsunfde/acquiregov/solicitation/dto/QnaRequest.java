package com.karsunfde.acquiregov.solicitation.dto;

/**
 * Vendor Q&A submission DTO.
 *
 * ⚠ Item 9 — {@code question} accepts raw HTML; feeds /answer-qa via the
 * ai-orchestrator (prompt-injection-via-stored-content target).
 */
public class QnaRequest {
    private String question;
    private String vendorId;

    public QnaRequest() {}

    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
}
