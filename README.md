# TaskPulse

> A full-stack task management application with a web interface for creating, tracking and managing personal tasks, backed by a production-oriented FastAPI API.

[![CI/CD](https://github.com/sm1le-devops/TaskPulse/actions/workflows/ci.yml/badge.svg)](https://github.com/sm1le-devops/TaskPulse/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-87.03%25-brightgreen)](#)
[![Python](https://img.shields.io/badge/python-3.12-blue)](#)

**Live Demo:** https://taskpulse-f5zy.onrender.com/

## ⚡ Stack

`Python 3.12` · `FastAPI` · `PostgreSQL` · `SQLAlchemy` · `Redis` · `Celery` · `Docker` · `Pytest` · `GitHub Actions`

## 📊 Key Numbers

| Metric                |             Value |
| --------------------- | ----------------: |
| Tests                 |            **62** |
| Coverage              |        **87.03%** |
| CI threshold          |           **85%** |
| Rate limit            | **20 req/min/IP** |
| Failed login attempts |             **5** |
| Access token          |        **15 min** |
| Refresh token         |        **7 days** |
| Idempotency window    |        **1 hour** |
| Task queries          |    **≤2 SELECTs** |

## 🏗️ Architecture

```text
                              ┌──────────────────┐
                              │      Client      │
                              │    Web Browser   │
                              └────────┬─────────┘
                                       │ HTTPS
                                       ▼
                              ┌──────────────────┐
                              │     FastAPI      │
                              │                  │
                              │ Auth · Tasks     │
                              │ Reports · RBAC   │
                              │ CSRF             │
                              └───────┬─────┬────┘
                                      │     │
                         ┌────────────┘     └────────────┐
                         ▼                               ▼
                ┌─────────────────┐             ┌─────────────────┐
                │   PostgreSQL    │             │      Redis      │
                │                 │             │                 │
                │ Users           │             │ Cache           │
                │ Tasks           │             │ Rate limiting   │
                │ Reports         │             │ Login attempts  │
                │ Refresh tokens  │             │ Idempotency     │
                └─────────────────┘             │ Celery Broker   │
                                                └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │ Celery Worker   │
                                                │                 │
                                                │ Report jobs     │
                                                │ Background work │
                                                └────────┬────────┘
                                                         │
                                                         ▼
                                                    PostgreSQL


                         ┌──────────────────────────┐
                         │      GitHub Actions      │
                         │                          │
                         │ Tests · Coverage         │
                         │ PostgreSQL · Redis       │
                         │ Alembic · Deploy         │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                                  Production
```

## 🔐 Security

* JWT authentication with **HttpOnly cookies**
* **Refresh token rotation**
* **CSRF protection**
* **RBAC + IDOR protection**
* Redis **rate limiting**
* Login **brute-force protection**
* bcrypt password hashing
* Secure / SameSite cookies
* Security headers + CSP
* User-level data isolation

## ⚙️ Engineering Highlights

**Redis**

`Caching` · `Rate Limiting` · `Login Protection` · `Idempotency` · `Celery Broker`

**Celery**

Long-running report generation runs asynchronously:

```text
POST /reports/generate
        │
        ▼
Idempotency check
        │
        ▼
Create task
        │
        ▼
Celery Worker
        │
        ▼
Background report generation
```

**Idempotency**

`Idempotency-Key` prevents duplicate report jobs for the same user within **1 hour**.

Production verified: the same key produced **one Celery task instead of two**.

Uses atomic Redis `SET NX EX`.

**N+1 Protection**

Task listing is regression-tested to stay within **≤2 SELECT queries**.

## 🧪 Testing & CI/CD

```text
Git Push
   │
   ▼
GitHub Actions
   │
   ├── PostgreSQL + Redis
   ├── Alembic migrations
   ├── Pytest
   └── Coverage ≥ 85%
          │
          ▼
      Production
```

**62 tests · 87.03% coverage**

Tests cover authentication, authorization, CSRF, Redis, Celery, idempotency, task isolation, reports and N+1 protection.

## 🛠️ Run Locally

```bash
git clone <your-repository>
cd TaskPulse
docker compose up --build
```

**App:** `http://localhost:8000`
**Swagger:** `http://localhost:8000/docs`
