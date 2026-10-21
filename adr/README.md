# 📐 Python Shared Architecture Decision Records (ADRs)

This directory contains formal Architecture Decision Records (ADRs) for `python-shared` and monorepo cross-cutting standards.

---

## 📚 ADR Index

| ADR | Title | Scope / Topics | Status | Date |
|---|---|---|---|---|
| [**0001**](./0001-declarative-feature-http-configuration-and-usage.md) | Declarative Feature HTTP Configuration (`http-config.yml`) and Composable Pipeline Client Usage | `http-config.yml`, `ResilientHttpClient`, 3 Process Profiles, Circuit Breaker, Rate Limiting | Accepted | 2026-10-21 |
| [**0002**](./0002-declarative-feature-server-configuration-and-usage.md) | Declarative Feature Server Configuration (`server-config.yml`) and FastAPI Middleware Lifecycle Usage | `server-config.yml`, `ServerPolicySnapshot`, `CorrelationAndTelemetryMiddleware`, CEL Validation, Lifecycle Drain | Accepted | 2026-10-21 |
