package com.karsunfde.acquiregov.solicitation.dto;

/**
 * Agency answer to a vendor question.
 *
 * ⚠ Item 9 — {@code answer} accepts raw HTML; rendered verbatim on publish.
 */
public class QnaAnswerRequest {
    private String answer;

    public QnaAnswerRequest() {}

    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }
}
