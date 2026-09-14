# TaskPulse

**Production-oriented FastAPI backend focused on security, async processing, caching, testing and performance.**

[![CI](https://github.com/sm1le-devops/TaskPulse/actions/workflows/ci.yml/badge.svg)](https://github.com/sm1le-devops/TaskPulse/actions)

**Live Demo:** https://taskpulse-f5zy.onrender.com/

## Stack

`Python 3.12` · `FastAPI` · `PostgreSQL` · `SQLAlchemy` · `Redis` · `Celery` · `Docker` · `Pytest` · `CI/CD`

## What I Built

* JWT authentication with **HttpOnly cookies**
* **Refresh token rotation**
* **CSRF protection**
* Redis-based **IP rate limiting**
* Redis **response caching**
* Celery background jobs
* PostgreSQL + SQLAlchemy
* User/task **data isolation**
* Role-based access control
* Structured application logging
* Dockerized development environment
* Automated tests and CI/CD

## Engineering Highlights

### Performance

Local benchmark using **100 sequential requests**:

| Endpoint      |     Avg |         P95 |      Max |
| ------------- | ------: | ----------: | -------: |
| `GET /health` | 1.34 ms | **1.56 ms** | 13.12 ms |
| `GET /tasks/` | 4.41 ms | **4.93 ms** |  7.27 ms |

`GET /tasks/` was benchmarked with **20 persisted tasks** and Redis caching enabled.

> Benchmarks were run locally with FastAPI TestClient and are intended for regression tracking, not production capacity estimates.

### Test Suite

* **32 tests passing**
* **89% code coverage**
* Authentication & authorization
* CSRF validation
* Refresh token flow
* User data isolation
* Redis rate limiting & TTL
* Celery task execution
* N+1 query detection
* API performance benchmarks

### Query Efficiency

`GET /tasks/` is protected against N+1 queries:

**≤ 2 SELECT queries** for the task list.

### Rate Limiting

Redis-based IP rate limiter:

```text
20 requests / minute / IP
21st request → HTTP 429
TTL → 60 seconds
```

## Test Optimization

The test suite initially suffered from slow Redis operations and duplicated test database configuration.

I fixed these bottlenecks by:

* separating host and Docker Redis configuration
* adding Redis connection/socket timeouts
* migrating Redis operations to `redis.asyncio`
* managing Redis lifecycle through FastAPI lifespan
* isolating Redis state between tests
* mocking non-essential background email tasks
* centralizing shared test infrastructure in `tests/conftest.py`
* using a single shared SQLite test engine

Current result:

```text
32 passed in 6.54s
89% coverage
```

> I don't just use frameworks — I measure bottlenecks, fix them and verify the result.

## Architecture

```text
Client
   │
   ▼
FastAPI
   │
   ├── Authentication / Authorization
   │
   ├── Middleware
   │     ├── CSRF
   │     └── Rate Limiting
   │
   ├── Redis
   │     ├── Response Cache
   │     └── Rate Limits
   │
   ├── PostgreSQL
   │     └── Persistent Data
   │
   └── Celery
         └── Background Tasks
```

## Testing

The test suite covers:

* User registration and authentication
* Login and refresh token flow
* CSRF protection
* Authorization and role-based access
* Task creation and retrieval
* User data isolation
* Report generation
* Celery background tasks
* Redis rate limiting
* Redis TTL behavior
* N+1 query detection
* Health endpoint
* API performance

## Focus

**Backend Engineering · API Design · Security · Async Processing · Databases · Caching · Testing · Performance**
