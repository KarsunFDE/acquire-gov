package com.karsunfde.acquiregov.gateway;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;

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
            .authorizeExchange(exchanges -> exchanges
                .pathMatchers("/actuator/**").permitAll()
                // ↓↓↓ ITEM 1 — the public route bypasses real auth.
                .pathMatchers("/api/public/**").permitAll()
                .anyExchange().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> {}))
            // ↓↓↓ ITEM 1 — the skip filter accepts unsigned JWTs on /api/public/**.
            .addFilterBefore(new JwtSignatureSkipFilter(),
                org.springframework.security.config.web.server.SecurityWebFiltersOrder.AUTHENTICATION);

        return http.build();
    }
}
