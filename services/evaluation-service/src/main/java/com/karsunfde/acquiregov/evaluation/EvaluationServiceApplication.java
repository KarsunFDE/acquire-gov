package com.karsunfde.acquiregov.evaluation;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.web.client.RestTemplate;

/**
 * acquire-gov — Evaluation Service.
 *
 * Coordinates evaluation panels for solicitations. Calls solicitation-service
 * synchronously to fetch solicitation data (⚠ no circuit breaker — Item 3).
 *
 * Brownfield-debt items in this service:
 *   - Item 3 — No Resilience4j circuit breaker on outbound calls
 *   - Item 6 — Logs traceId (inconsistent with X-Request-ID / correlationId)
 *   - Item 11 — Dockerfile uses :latest
 *
 * {@code @EnableScheduling} is required by the chaos-profile cron trigger in
 * {@code com.karsunfde.acquiregov.evaluation.chaos.EvaluatorLoadStormInjector}.
 * Enabling it on the default profile is harmless — no other {@code @Scheduled}
 * methods exist in this service, and the chaos bean itself is profile-gated.
 */
@SpringBootApplication
@EnableScheduling
public class EvaluationServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(EvaluationServiceApplication.class, args);
    }

    /**
     * ⚠ DELIBERATE — Item 3: no timeout configuration, no error handler, no
     * circuit breaker wrapper. A slow solicitation-service will pile threads
     * on this RestTemplate.
     */
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
