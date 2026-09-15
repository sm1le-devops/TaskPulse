import os

import redis

def test_security_headers(client):
    response = client.get("/health")

    assert response.status_code == 200

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert (
        response.headers["Referrer-Policy"]
        == "strict-origin-when-cross-origin"
    )

    csp = response.headers["Content-Security-Policy"]

    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    
def test_cors_allows_known_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://taskpulse-f5zy.onrender.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://taskpulse-f5zy.onrender.com"
    )
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil-example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
    
def test_login_bruteforce_protection(client):
    email = "bruteforce@example.com"
    password = "password123"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    # First 5 failed attempts are allowed.
    for _ in range(5):
        response = client.post(
            "/auth/login",
            data={
                "username": email,
                "password": "wrong-password",
            },
        )

        assert response.status_code == 401

    # 6th failed attempt is rate limited.
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 429
    
def test_successful_login_resets_failed_attempts(client):
    email = "reset@example.com"
    password = "password123"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    # Create 4 failed attempts.
    for _ in range(4):
        response = client.post(
            "/auth/login",
            data={
                "username": email,
                "password": "wrong-password",
            },
        )

        assert response.status_code == 401

    # Successful login must reset the Redis counter.
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    # We can fail 5 more times after the reset.
    for _ in range(5):
        response = client.post(
            "/auth/login",
            data={
                "username": email,
                "password": "wrong-password",
            },
        )

        assert response.status_code == 401

    # The next failed attempt is blocked.
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 429

def test_login_bruteforce_key_has_ttl(client):
    email = "ttl@example.com"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "password123",
        },
    )

    assert response.status_code == 200

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401

    redis_client = redis.Redis.from_url(
        os.environ["REDIS_URL_BROKER"],
        decode_responses=True,
    )

    client_ip = "testclient"
    login_key = f"login:failed:{client_ip}:{email.lower()}"

    ttl = redis_client.ttl(login_key)

    assert 0 < ttl <= 15 * 60

    redis_client.close()
    
def test_logout_without_csrf_returns_403(client):
    email = "logout-csrf@example.com"
    password = "password123"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    response = client.post("/auth/logout")

    assert response.status_code == 403
    
def test_logout_with_valid_csrf(client):
    email = "logout-valid@example.com"
    password = "password123"

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    csrf_token = response.json()["csrf_token"]

    response = client.post(
        "/auth/logout",
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"