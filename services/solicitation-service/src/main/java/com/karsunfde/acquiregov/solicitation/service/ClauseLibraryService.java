package com.karsunfde.acquiregov.solicitation.service;

import com.karsunfde.acquiregov.solicitation.model.ClauseLibraryEntry;
import com.karsunfde.acquiregov.solicitation.repository.ClauseLibraryRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

/**
 * Clause-library lookup. Lexical search only — cohort wires Atlas Vector
 * Search hybrid retrieval in W2.
 */
@Service
public class ClauseLibraryService {

    private final ClauseLibraryRepository repo;

    @Autowired
    public ClauseLibraryService(ClauseLibraryRepository repo) {
        this.repo = repo;
    }

    public Optional<ClauseLibraryEntry> findByClauseId(String clauseId) {
        return repo.findByClauseId(clauseId);
    }

    public List<ClauseLibraryEntry> search(String fragment, String farPart) {
        if (farPart != null && !farPart.isEmpty()) {
            return repo.findByFarPart(farPart);
        }
        if (fragment != null && !fragment.isEmpty()) {
            return repo.findByTitleContainingIgnoreCase(fragment);
        }
        return repo.findAll();
    }
}
