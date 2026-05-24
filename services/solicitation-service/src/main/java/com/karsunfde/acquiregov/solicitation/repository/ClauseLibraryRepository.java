package com.karsunfde.acquiregov.solicitation.repository;

import com.karsunfde.acquiregov.solicitation.model.ClauseLibraryEntry;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

/**
 * Clause-library repository. W2 RAG corpus.
 *
 * Vector-search method ({@code searchByEmbedding}) is NOT defined here — the
 * cohort wires that up in W2 Tue using Atlas Vector Search via MongoTemplate.
 * What lives here is the lexical-only fallback the brownfield stack ships
 * with.
 */
public interface ClauseLibraryRepository extends MongoRepository<ClauseLibraryEntry, String> {

    Optional<ClauseLibraryEntry> findByClauseId(String clauseId);

    List<ClauseLibraryEntry> findByFarPart(String farPart);

    /** Naive lexical match — cohort upgrades to hybrid in W2. */
    List<ClauseLibraryEntry> findByTitleContainingIgnoreCase(String fragment);
}
