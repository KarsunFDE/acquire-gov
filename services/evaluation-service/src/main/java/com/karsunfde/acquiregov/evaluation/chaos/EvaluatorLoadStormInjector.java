package com.karsunfde.acquiregov.evaluation.chaos;

import com.karsunfde.acquiregov.evaluation.client.SolicitationClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Profile;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * W4 Fri Mid-Sprint Surprise load-storm injector — INSTRUCTOR-ONLY.
 *
 * <p>Reproduces the canonical Workflow 4 + Item 3 incident shape per
 * {@code weeks/W04/war-room/Fri-mid-sprint-surprise.md} (D-049 + D-060).
 *
 * <p><b>Two hard gates against accidental production activation:</b>
 * <ol>
 *   <li>{@code @Profile("chaos")} — bean is not in the context unless
 *       {@code SPRING_PROFILES_ACTIVE=chaos}.</li>
 *   <li>{@code @ConditionalOnProperty} — even on chaos profile, bean
 *       refuses to wire unless {@code chaos.evaluator-load-storm.enabled=true}.</li>
 * </ol>
 *
 * <p>What it does: at the configured cron tick (or via manual trigger from
 * {@link ChaosTriggerController}), spins up N evaluator-simulating threads
 * that loop calling {@link SolicitationClient#getSolicitation(String)} for
 * the configured solicitation id. Sustained for the configured duration,
 * then quiesces. Designed to saturate evaluation-service's outbound
 * RestTemplate connection pool against solicitation-service — which lacks
 * a circuit breaker (Item 3). Cascade reproduces.
 *
 * <p>NOT a load test. NOT a benchmark tool. Strictly the instructor-side
 * trigger for a single, scripted incident-response exercise.
 */
@Component
@Profile("chaos")
@ConditionalOnProperty(
    name = "chaos.evaluator-load-storm.enabled",
    havingValue = "true"
)
public class EvaluatorLoadStormInjector {

    private static final Logger log = LoggerFactory.getLogger(EvaluatorLoadStormInjector.class);

    private final SolicitationClient solicitationClient;

    @Value("${chaos.evaluator-load-storm.target-solicitation-id}")
    private String targetSolicitationId;

    @Value("${chaos.evaluator-load-storm.concurrent-threads:50}")
    private int concurrentThreads;

    @Value("${chaos.evaluator-load-storm.duration-seconds:240}")
    private int durationSeconds;

    @Value("${chaos.evaluator-load-storm.request-interval-millis:50}")
    private long requestIntervalMillis;

    private final AtomicBoolean stormInFlight = new AtomicBoolean(false);
    private ExecutorService executor;

    public EvaluatorLoadStormInjector(SolicitationClient solicitationClient) {
        this.solicitationClient = solicitationClient;
        log.warn("[CHAOS] EvaluatorLoadStormInjector active. Profile=chaos, flag=true. "
                + "This service is in INSTRUCTOR CHAOS MODE — do not run in production.");
    }

    /**
     * Cron-triggered entry point. Default fires Fri 09:00 local; instructor
     * may override via {@code chaos.evaluator-load-storm.schedule-cron}.
     */
    @Scheduled(cron = "${chaos.evaluator-load-storm.schedule-cron:0 0 9 * * FRI}")
    public void scheduledStorm() {
        triggerStorm("scheduled");
    }

    /**
     * Manual trigger entry point. Called by {@link ChaosTriggerController}
     * during instructor prep verification.
     *
     * @return one-line status message
     */
    public String triggerStorm(String source) {
        if (!stormInFlight.compareAndSet(false, true)) {
            String msg = "[CHAOS] storm already in flight; ignoring " + source + " trigger";
            log.warn(msg);
            return msg;
        }
        log.warn("[CHAOS] storm STARTING via {} — threads={} duration={}s target={} interval={}ms",
                source, concurrentThreads, durationSeconds, targetSolicitationId, requestIntervalMillis);

        executor = Executors.newFixedThreadPool(concurrentThreads);
        AtomicLong requestCount = new AtomicLong();
        AtomicLong errorCount = new AtomicLong();
        long deadlineNanos = System.nanoTime() + TimeUnit.SECONDS.toNanos(durationSeconds);

        for (int i = 0; i < concurrentThreads; i++) {
            final int threadIndex = i;
            executor.submit(() -> stormLoop(threadIndex, deadlineNanos, requestCount, errorCount));
        }

        executor.shutdown();
        new Thread(() -> awaitCompletion(requestCount, errorCount), "chaos-storm-watcher").start();
        return "[CHAOS] storm started via " + source + " — target=" + targetSolicitationId
                + " threads=" + concurrentThreads + " duration=" + durationSeconds + "s";
    }

    private void stormLoop(int threadIndex, long deadlineNanos,
                           AtomicLong requestCount, AtomicLong errorCount) {
        while (System.nanoTime() < deadlineNanos && !Thread.currentThread().isInterrupted()) {
            try {
                solicitationClient.getSolicitation(targetSolicitationId);
                requestCount.incrementAndGet();
            } catch (RuntimeException ex) {
                errorCount.incrementAndGet();
                // intentional: swallow upstream errors. The point of the
                // storm is to load the upstream — exceptions are signal,
                // not a reason to stop.
            }
            try {
                TimeUnit.MILLISECONDS.sleep(requestIntervalMillis);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                return;
            }
        }
        log.debug("[CHAOS] thread {} reached deadline", threadIndex);
    }

    private void awaitCompletion(AtomicLong requestCount, AtomicLong errorCount) {
        try {
            if (!executor.awaitTermination(durationSeconds + 60L, TimeUnit.SECONDS)) {
                log.warn("[CHAOS] executor did not terminate cleanly; forcing shutdown");
                executor.shutdownNow();
            }
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            executor.shutdownNow();
        } finally {
            stormInFlight.set(false);
            log.warn("[CHAOS] storm COMPLETE — requests={} errors={}",
                    requestCount.get(), errorCount.get());
        }
    }

    @PreDestroy
    public void shutdown() {
        if (executor != null && !executor.isTerminated()) {
            log.warn("[CHAOS] shutdown — interrupting in-flight storm executor");
            executor.shutdownNow();
        }
    }

    public boolean isStormInFlight() {
        return stormInFlight.get();
    }
}
