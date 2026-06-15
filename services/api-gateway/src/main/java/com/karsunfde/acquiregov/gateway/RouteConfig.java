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
            // ai-orchestrator mounts its routers at root (/draft-solicitation/**,
            // /retrieve, /ingest/**), so strip the /api/ai prefix (2 segments)
            // the SPA addresses it by. The Spring services serve under their full
            // /api/... path, hence no StripPrefix on those routes.
            .route("ai",            r -> r.path("/api/ai/**")
                                          .filters(f -> f
                                              .stripPrefix(2)
                                              // The orchestrator (FastAPI CORSMiddleware) also emits
                                              // CORS headers; without dedupe the gateway forwards those
                                              // AND adds its own → "Access-Control-Allow-Origin contains
                                              // multiple values" and the browser blocks the response.
                                              // RETAIN_UNIQUE collapses identical values to one.
                                              .dedupeResponseHeader(
                                                  "Access-Control-Allow-Origin Access-Control-Allow-Credentials",
                                                  "RETAIN_UNIQUE"))
                                          .uri(aiUrl))
            // Item 1 — public path forwards to solicitation-service after signature-skip.
            .route("public",        r -> r.path("/api/public/**").uri(solicitationUrl))
            .build();
    }
}
