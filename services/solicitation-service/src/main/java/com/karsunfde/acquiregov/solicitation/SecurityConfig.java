package com.karsunfde.acquiregov.solicitation;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Dev-default security: assume requests passed through the api-gateway and
 * trust them. Downstream services do not re-validate the JWT — which is part
 * of why Item 1 (gateway signature-skip) is so dangerous.
 *
 * For W1 day-1 smoke-test purposes, we permit all so the cohort can curl
 * endpoints directly during the brownfield-debt walkthrough. Real prod config
 * would re-validate.
 */
@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
        return http.build();
    }
}
