package com.karsunfde.acquiregov.evaluation.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * Calls ai-orchestrator for SSDD draft + factor-suggest narrative.
 *
 * ⚠ Item 3 reinforcement — same RestTemplate, no circuit breaker.
 * ⚠ Item 6 — no correlation-id forwarded.
 */
@Component
public class AiOrchestratorClient {

    private static final Logger log = LoggerFactory.getLogger(AiOrchestratorClient.class);

    private final RestTemplate restTemplate;

    @Value("${ai.orchestrator.url:http://ai-orchestrator:8000}")
    private String aiUrl;

    @Autowired
    public AiOrchestratorClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> draftSsdd(String evaluationId) {
        Map<String, Object> body = new HashMap<>();
        body.put("topic", "SSDD for evaluation " + evaluationId);
        body.put("constraints", "FAR 15.308 tradeoff narrative");
        log.info("calling ai-orchestrator /eval/ssdd-draft evaluationId={} traceId=N/A", evaluationId);
        return restTemplate.postForObject(aiUrl + "/eval/ssdd-draft", body, Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> factorSuggest(String proposalText, String factorId) {
        Map<String, Object> body = new HashMap<>();
        body.put("topic", "factor " + factorId);
        body.put("constraints", proposalText);
        return restTemplate.postForObject(aiUrl + "/eval/factor-suggest", body, Map.class);
    }
}
