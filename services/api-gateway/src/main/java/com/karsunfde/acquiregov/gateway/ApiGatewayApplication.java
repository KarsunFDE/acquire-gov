package com.karsunfde.acquiregov.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * acquire-gov — API Gateway.
 *
 * Routes requests from the Angular SPA to the downstream Spring Boot services
 * (solicitation-service, evaluation-service) and the Python AI orchestrator.
 *
 * DELIBERATE BROWNFIELD DEBT (annotated for cohort discovery in W1 Tue):
 *   - {@link SecurityConfig} skips JWT signature verification on /api/public/**
 *     (Item 1 in docs/brownfield-debt.md).
 *   - Correlation-ID is logged as X-Request-ID — inconsistent with the other
 *     services (Item 6 in docs/brownfield-debt.md).
 *   - No rate limiting.
 *   - Dockerfile uses :latest base image (Item 11).
 */
@SpringBootApplication
public class ApiGatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(ApiGatewayApplication.class, args);
    }
}
