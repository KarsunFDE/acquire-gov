package com.karsunfde.acquiregov.solicitation.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDate;

/**
 * FAR / DFARS clause-library entry. W2 RAG corpus source.
 *
 * Atlas Vector Search index on {@code body} for hybrid lexical+vector
 * retrieval (W2 Wed introduces the agencyVisibility filter that closes
 * Item 10 on retrieval).
 */
@Document(collection = "clause_library")
public class ClauseLibraryEntry {

    @Id
    private String id;

    private String clauseId;     // e.g., 52.212-4
    private String farPart;      // e.g., FAR, DFARS
    private String title;
    private String body;
    private LocalDate lastRevised;

    public ClauseLibraryEntry() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getClauseId() { return clauseId; }
    public void setClauseId(String clauseId) { this.clauseId = clauseId; }
    public String getFarPart() { return farPart; }
    public void setFarPart(String farPart) { this.farPart = farPart; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getBody() { return body; }
    public void setBody(String body) { this.body = body; }
    public LocalDate getLastRevised() { return lastRevised; }
    public void setLastRevised(LocalDate lastRevised) { this.lastRevised = lastRevised; }
}
