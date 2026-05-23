package com.karsunfde.acquiregov.solicitation;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;

/**
 * Dev-default security: assume requests passed through the api-gateway and
 * trust them. Downstream services do not re-validate the JWT — which is part
 * of why Item 1 (gateway signature-skip) is so dangerous.
 *
 * For W1 day-1 smoke-test purposes, we permit all so the cohort can curl
 * endpoints directly during the brownfield-debt walkthrough. Real prod config
 * would re-validate.
 *
 * Era-authentic Karsun-legacy pattern: {@link WebSecurityConfigurerAdapter}
 * + {@code configure(HttpSecurity)} + {@code authorizeRequests().antMatchers()}.
 * Deprecated in Spring Security 5.7 (in favor of the {@code SecurityFilterChain}
 * bean style), but it remains the dominant pattern across real Karsun federal
 * estates on Boot 2.3–2.5 / Security 5.4 era. Cohort migrates this to the
 * modern bean DSL during the W4–W5 modernization arc.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .csrf().disable()
            .authorizeRequests()
                .anyRequest().permitAll();
    }
}
