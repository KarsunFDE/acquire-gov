# ⚠ DELIBERATE BROWNFIELD DEBT — Item 11 in docs/brownfield-debt.md
# Uses :latest base image. Cohort fixes in W4 Wed (OWASP LLM03 Supply Chain).
FROM eclipse-temurin:latest AS build
WORKDIR /workspace

# Copy maven wrapper + pom first for layer caching
COPY pom.xml .
COPY src ./src

# Use system maven via the eclipse-temurin image — install on the fly.
RUN apt-get update && apt-get install -y maven && rm -rf /var/lib/apt/lists/*
RUN mvn -B -DskipTests package

FROM eclipse-temurin:latest
WORKDIR /app
COPY --from=build /workspace/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
