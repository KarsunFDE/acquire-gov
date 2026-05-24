package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/**
 * Vendor-submitted question + agency-published answer for a solicitation.
 *
 * Q&A is part of FAR 15.201 pre-solicitation exchanges. Vendor identity is
 * redacted on publish (other vendors see the Q + A but not the asker).
 *
 * ⚠ Item 9 — {@code question} + {@code answer} are raw text fed into
 * ai-orchestrator for /answer-qa drafting (prompt-injection-via-stored-content).
 */
@Document(collection = "qna")
public class Qna {

    @Id
    private String id;

    private String solicitationId;
    private String agencyId;

    /** ⚠ Item 9 — raw HTML accepted. */
    private String question;

    /** ⚠ Item 9 — raw HTML accepted. */
    private String answer;

    private String vendorId; // redacted on publish
    private String status;   // SUBMITTED / DRAFTED / PUBLISHED
    private Instant submittedAt;
    private Instant answeredAt;

    public Qna() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getSolicitationId() { return solicitationId; }
    public void setSolicitationId(String solicitationId) { this.solicitationId = solicitationId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }
    public String getVendorId() { return vendorId; }
    public void setVendorId(String vendorId) { this.vendorId = vendorId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Instant getSubmittedAt() { return submittedAt; }
    public void setSubmittedAt(Instant submittedAt) { this.submittedAt = submittedAt; }
    public Instant getAnsweredAt() { return answeredAt; }
    public void setAnsweredAt(Instant answeredAt) { this.answeredAt = answeredAt; }
}
