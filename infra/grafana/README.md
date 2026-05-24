# Grafana — W4 Fri Mid-Sprint Surprise dashboard

Instructor-only. Pre-seed reference for the load-incident dashboard described
in `weeks/W04/war-room/Fri-mid-sprint-surprise.md` §0.

## What's in here

- `dashboards/acquire-gov-eval-load.json` — 4-panel Grafana dashboard model
  (Grafana 10+). Three required signals + one supporting outbound-latency
  panel. Targets two datasources: Prometheus (JVM + HTTP client metrics) and
  Loki (audit-log + chaos-storm annotations).

## What's NOT in here (and why)

- No `docker-compose` for Prometheus / Grafana / Loki / Promtail.
- No micrometer-prometheus dependency added to `evaluation-service` /
  `solicitation-service` `pom.xml` — that's W5 AIOps work the cohort does
  themselves (the "we don't have a scrape endpoint" gap is intentional).

The instructor stands up their own observability stack out-of-band for the
W4 Fri exercise, points it at acquire-gov, and imports this dashboard.
Reproducible across cohorts because the dashboard JSON is in-repo.

## Instructor wiring (one-time per delivery host)

1. **Stand up Prometheus + Grafana + Loki + Promtail** alongside acquire-gov.
   Any standard compose recipe works (e.g., `grafana/grafana-oss:10.4.0` +
   `prom/prometheus:v2.51.0` + `grafana/loki:2.9.0` + `grafana/promtail:2.9.0`).
2. **Expose Prometheus scrape on the two Java services.** The cohort has
   not added micrometer-prometheus yet (intentional gap). For the W4 Fri
   exercise only, add the dependency + actuator exposure to your local
   instructor build — do **not** commit:
   ```xml
   <dependency>
     <groupId>io.micrometer</groupId>
     <artifactId>micrometer-registry-prometheus</artifactId>
   </dependency>
   ```
   ```yaml
   # application-chaos.yml additive override (instructor-local only)
   management:
     endpoints:
       web:
         exposure:
           include: health,info,prometheus
   ```
3. **Add scrape config to your Prometheus.** Targets
   `evaluation-service:8082` and `solicitation-service:8081`, path
   `/actuator/prometheus`, label `application` matching the dashboard
   queries.
4. **Point Promtail at the service log streams** with labels
   `service=evaluation-service` and `service=solicitation-service`.
5. **Import the dashboard.** Grafana → Dashboards → Import → upload
   `dashboards/acquire-gov-eval-load.json`. Resolve the two datasource
   variables (`DS_PROMETHEUS`, `DS_LOKI`) to your stack.
6. **Verify pre-stage.** Trigger the storm manually the day before:
   ```bash
   curl -X POST http://evaluation-service:8082/admin/chaos/storm/trigger
   ```
   Watch the dashboard for all three signals firing in sequence.

## Re-use across cohorts (D-049 reproducibility)

Dashboard JSON is locked per D-049 + D-060. For Cohort #2+:

- Re-import the same JSON.
- Update the cohort delivery date in your instructor runbook.
- Re-confirm the `chaos.evaluator-load-storm.target-solicitation-id`
  exists in the test environment.

Do NOT mark the W4-MSS scenario as `used: true` — see
`weeks/W04/war-room/Fri-mid-sprint-surprise.md` §10.

## Dashboard signal timing

The narrative timeline (~09:03 / ~09:05 / ~09:07) in the panel titles is
the storyline anchor, not a real-time guarantee. Actual signal arrival
shifts with the storm parameters in `application-chaos.yml` (50 threads +
4-min sustain + 50ms inter-request delay). Reviewing this dashboard
post-exercise: align the cohort's `correlation_id`-traced timeline against
the actual Grafana time-axis, not the panel titles.
