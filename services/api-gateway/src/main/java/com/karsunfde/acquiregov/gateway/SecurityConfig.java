package com.karsunfde.acquiregov.gateway;

import java.util.List;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsConfigurationSource;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;

/**
 * Reactive security configuration for the API Gateway.
 *
 * ⚠ DELIBERATE BROWNFIELD DEBT — Item 1 in docs/brownfield-debt.md ⚠
 *
 * The gateway exposes a /api/public/** path that is intended for unauthenticated
 * "public" reads (e.g., catalog browsing). But the route is also wired so that
 * any JWT presented on that path is accepted WITHOUT signature verification:
 * {@link JwtSignatureSkipFilter} short-circuits the standard
 * spring-security-oauth2-resource-server validator.
 *
 * In practice this means a caller can mint a JWT with any claims (including
 * elevated roles) and have it accepted as long as it's structurally a JWT —
 * because the public path's filter accepts it without checking the signature,
 * and downstream services trust the upstream "this gateway already validated"
 * convention.
 *
 * Cohort finds this in W1 Tue brownfield-debt inventory; fix lands in W4 Wed
 * AI Security Engineering Day (OWASP LLM07/08 — tool-misuse prevention).
 *
 * What "fixed" looks like:
 *   - Delete {@link JwtSignatureSkipFilter}.
 *   - Route /api/public/** through the standard oauth2 resource-server JWT
 *     decoder (signature MUST verify against the JWKS).
 *   - Use {@code authorizeExchange().pathMatchers("/api/public/**").permitAll()}
 *     only for genuinely-anonymous reads; never for paths that resolve a user
 *     identity.
 */
@Configuration
@EnableWebFluxSecurity
public class SecurityConfig {

    @Bean
    public SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http) {
        http
            .csrf(csrf -> csrf.disable())
            // CORS must run before authorization so the browser preflight is
            // answered with the right headers (the SPA on :4200 calls the
            // gateway on :8080 — a cross-origin request).
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .authorizeExchange(exchanges -> exchanges
                .pathMatchers("/actuator/**").permitAll()
                // CORS preflight carries no credentials by design — it must
                // never hit the authenticated branch or the browser blocks the
                // real request. Permit OPTIONS everywhere.
                .pathMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                // ↓↓↓ ITEM 1 — the public route bypasses real auth.
                .pathMatchers("/api/public/**").permitAll()
                // ⚠ DEMO ONLY (2026-06-15) — the SPA has no auth wired yet
                // (real role-based gateway auth is M1 follow-up work). Permit
                // the AI routes so the frontend can exercise the orchestrator
                // end-to-end for the demo. REVERT before treating gateway auth
                // as enforced: drop this line and have the SPA attach a JWT.
                .pathMatchers("/api/ai/**").permitAll()
                .anyExchange().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> {}))
            // ↓↓↓ ITEM 1 — the skip filter accepts unsigned JWTs on /api/public/**.
            .addFilterBefore(new JwtSignatureSkipFilter(),
                org.springframework.security.config.web.server.SecurityWebFiltersOrder.AUTHENTICATION);

        return http.build();
    }

    /**
     * Permissive dev/demo CORS: any origin, the headers the SPA sends
     * (X-Tenant-ID, X-Request-ID, Content-Type, Authorization), all methods.
     * No credentials (the SPA sends bearer headers, not cookies), so a
     * wildcard origin is safe. Tighten {@code allowedOriginPatterns} to the
     * known SPA origin(s) for any non-dev deployment.
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration cfg = new CorsConfiguration();
        cfg.setAllowedOriginPatterns(List.of("*"));
        cfg.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        cfg.setAllowedHeaders(List.of("*"));
        cfg.setExposedHeaders(List.of("X-Request-ID"));
        cfg.setAllowCredentials(false);
        cfg.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", cfg);
        return source;
    }
}
