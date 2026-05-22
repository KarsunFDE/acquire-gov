# ⚠ NOTE: this Dockerfile was originally `FROM python:latest` — see Item 11
# in docs/brownfield-debt.md. It was hand-pinned to 3.11 in 2026-Q1 after
# numpy/pydantic-core wheels broke on python 3.14. The OTHER Dockerfiles
# (api-gateway, solicitation-service, evaluation-service, frontend) still
# carry the :latest debt. Cohort finds those in W4 Wed AI Security
# Engineering Day (OWASP LLM03 Supply Chain).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
