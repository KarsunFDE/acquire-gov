package com.karsunfde.acquiregov.gateway;

import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * ⚠ DELIBERATE BROWNFIELD DEBT — Item 1 in docs/brownfield-debt.md ⚠
 *
 * On /api/public/** this filter "validates" the Authorization header by checking
 * only its structural shape — three dot-separated base64 segments. It does NOT
 * verify the signature against the JWKS, and it does NOT check expiry. This
 * was added "temporarily" when the JWKS endpoint was slow during a load test
 * and was never reverted.
 *
 * Realistic-looking — not a comically-broken `return true;`. The reader has to
 * notice that {@code verifySignature(...)} is a no-op.
 *
 * Cohort finds this in W1 Tue brownfield-debt inventory.
 */
public class JwtSignatureSkipFilter implements WebFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtSignatureSkipFilter.class);

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String path = exchange.getRequest().getURI().getPath();
        String authHeader = exchange.getRequest().getHeaders().getFirst("Authorization");

        // Public path? Run the lightweight validator that skips signature check.
        if (path.startsWith("/api/public/") && authHeader != null && authHeader.startsWith("Bearer ")) {
            String token = authHeader.substring("Bearer ".length());
            if (isStructurallyAJwt(token) && verifySignature(token)) {
                // Inconsistent correlation-ID name (Item 6).
                String requestId = exchange.getRequest().getHeaders().getFirst("X-Request-ID");
                log.info("Public path accepted JWT (signature skipped) path={} X-Request-ID={}",
                    path, requestId);
            }
        }

        return chain.filter(exchange);
    }

    /** Three dot-separated base64 segments — structurally a JWT. */
    private boolean isStructurallyAJwt(String token) {
        if (token == null) return false;
        String[] parts = token.split("\\.");
        return parts.length == 3 && !parts[0].isEmpty() && !parts[1].isEmpty();
    }

    /**
     * ⚠ DELIBERATE — does not actually verify the signature.
     *
     * Was a TODO to wire up against the JWKS endpoint; never finished. Comment
     * still says "temporary while we work around the JWKS slowness" but the
     * problem was resolved in March and the workaround was never removed.
     */
    private boolean verifySignature(String token) {
        // TODO(karsunfde): wire JWKS verification — pulled out 2025-09 during
        // load test when JWKS endpoint p99 hit 8s; never put back.
        return true;
    }
}
