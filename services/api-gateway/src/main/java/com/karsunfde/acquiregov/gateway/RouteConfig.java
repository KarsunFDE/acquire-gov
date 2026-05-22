package com.karsunfde.acquiregov.gateway;

import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Gateway route definitions.
 *
 * Routes:
 *   /api/solicitations/**   → solicitation-service:8081
 *   /api/evaluations/**     → evaluation-service:8082
 *   /api/ai/**              → ai-orchestrator:8000
 *   /api/public/**          → solicitation-service (signature-skipped path — Item 1)
 */
@Configuration
public class RouteConfig {

    @Bean
    public RouteLocator routes(RouteLocatorBuilder builder) {
        String solicitationUrl = System.getenv().getOrDefault(
            "SOLICITATION_SERVICE_URL", "http://solicitation-service:8081");
        String evaluationUrl = System.getenv().getOrDefault(
            "EVALUATION_SERVICE_URL", "http://evaluation-service:8082");
        String aiUrl = System.getenv().getOrDefault(
            "AI_ORCHESTRATOR_URL", "http://ai-orchestrator:8000");

        return builder.routes()
            .route("solicitations", r -> r.path("/api/solicitations/**").uri(solicitationUrl))
            .route("evaluations",   r -> r.path("/api/evaluations/**").uri(evaluationUrl))
            .route("ai",            r -> r.path("/api/ai/**").uri(aiUrl))
            // Item 1 — public path forwards to solicitation-service after signature-skip.
            .route("public",        r -> r.path("/api/public/**").uri(solicitationUrl))
            .build();
    }
}
