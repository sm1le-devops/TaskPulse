import time


# ============================================================
# HELPERS
# ============================================================

def register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "performance@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200


def login_user(client):
    response = client.post(
        "/auth/login",
        data={
            "username": "performance@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    csrf_token = response.cookies.get("csrf_token")

    assert csrf_token is not None

    return csrf_token


def create_tasks(client, csrf_token, count=20):
    """
    Create persisted tasks used by the performance benchmark.
    """
    for i in range(count):
        response = client.post(
            "/tasks/",
            json={
                "title": f"Performance Task {i}",
                "priority": i,
            },
            headers={
                "X-CSRF-Token": csrf_token,
            },
        )

        assert response.status_code == 200


# ============================================================
# BENCHMARK UTILITIES
# ============================================================

def benchmark_tasks_endpoint(client, requests=100):
    times = []

    for _ in range(requests):
        start = time.perf_counter()

        response = client.get("/tasks/")

        elapsed = time.perf_counter() - start

        assert response.status_code == 200

        times.append(elapsed)

    times.sort()

    average = sum(times) / len(times)
    minimum = times[0]
    maximum = times[-1]

    p95_index = int(len(times) * 0.95) - 1
    p95 = times[p95_index]

    return {
        "requests": requests,
        "average_ms": average * 1000,
        "min_ms": minimum * 1000,
        "max_ms": maximum * 1000,
        "p95_ms": p95 * 1000,
    }


# ============================================================
# HEALTH PERFORMANCE
# ============================================================

def test_health_performance(client, monkeypatch):
    """
    Benchmark /health without rate limiting.

    Rate limiting is disabled only for this benchmark
    to isolate endpoint latency.
    """
    monkeypatch.setenv("TESTING", "true")

    times = []

    for _ in range(100):
        start = time.perf_counter()

        response = client.get("/health")

        elapsed = time.perf_counter() - start

        assert response.status_code == 200

        times.append(elapsed)

    times.sort()

    average = sum(times) / len(times)
    p95 = times[int(len(times) * 0.95) - 1]

    print()
    print("========== HEALTH PERFORMANCE ==========")
    print(f"Requests : {len(times)}")
    print(f"Average  : {average * 1000:.2f} ms")
    print(f"Min      : {times[0] * 1000:.2f} ms")
    print(f"Max      : {times[-1] * 1000:.2f} ms")
    print(f"P95      : {p95 * 1000:.2f} ms")
    print("=========================================")

    assert p95 < 1000


# ============================================================
# TASKS PERFORMANCE
# ============================================================

def test_tasks_list_performance(client, monkeypatch):
    """
    Benchmark GET /tasks/ with persisted database records.

    Rate limiting is disabled only for the benchmark
    to measure endpoint performance independently.
    """
    monkeypatch.setenv("TESTING", "true")

    # Create test user
    register_user(client)

    # Authenticate
    csrf_token = login_user(client)

    # Create realistic database data
    create_tasks(
        client,
        csrf_token,
        count=20,
    )

    # Benchmark endpoint
    result = benchmark_tasks_endpoint(
        client,
        requests=100,
    )

    print()
    print("========== TASKS PERFORMANCE ==========")
    print(f"Requests : {result['requests']}")
    print(f"Average  : {result['average_ms']:.2f} ms")
    print(f"Min      : {result['min_ms']:.2f} ms")
    print(f"Max      : {result['max_ms']:.2f} ms")
    print(f"P95      : {result['p95_ms']:.2f} ms")
    print("========================================")

    # Safety threshold.
    # Actual measured performance is reported above.
    assert result["p95_ms"] < 1000