package com.karsunfde.acquiregov.evaluation.chaos;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * Manual trigger endpoint for instructor prep verification of the W4 Fri
 * Mid-Sprint Surprise load storm. Lets the instructor confirm the chaos
 * pipeline works end-to-end the day before the cohort exercise, without
 * waiting for the scheduled cron.
 *
 * <p>Triple-gated against accidental production exposure:
 * <ul>
 *   <li>{@code @Profile("chaos")} — only on chaos profile</li>
 *   <li>{@code chaos.evaluator-load-storm.enabled=true} — master flag</li>
 *   <li>{@code chaos.evaluator-load-storm.manual-trigger-endpoint-enabled=true}
 *       — separately revocable on hosts that should ONLY allow the
 *       scheduled trigger.</li>
 * </ul>
 *
 * <p>Endpoints:
 * <ul>
 *   <li>{@code POST /admin/chaos/storm/trigger} — fire the storm now</li>
 *   <li>{@code GET  /admin/chaos/storm/status} — is a storm in flight?</li>
 * </ul>
 */
@RestController
@RequestMapping("/admin/chaos/storm")
@Profile("chaos")
@ConditionalOnProperty(
    name = "chaos.evaluator-load-storm.manual-trigger-endpoint-enabled",
    havingValue = "true"
)
public class ChaosTriggerController {

    private static final Logger log = LoggerFactory.getLogger(ChaosTriggerController.class);

    private final EvaluatorLoadStormInjector injector;

    public ChaosTriggerController(EvaluatorLoadStormInjector injector) {
        this.injector = injector;
        log.warn("[CHAOS] ChaosTriggerController active at /admin/chaos/storm/* — instructor-only");
    }

    @PostMapping("/trigger")
    public ResponseEntity<Map<String, Object>> trigger() {
        String status = injector.triggerStorm("manual");
        Map<String, Object> body = new HashMap<>();
        body.put("status", status);
        body.put("inFlight", injector.isStormInFlight());
        return ResponseEntity.accepted().body(body);
    }

    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        Map<String, Object> body = new HashMap<>();
        body.put("inFlight", injector.isStormInFlight());
        return ResponseEntity.ok(body);
    }
}
