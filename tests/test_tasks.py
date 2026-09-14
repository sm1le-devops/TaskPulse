# ============================================================
# IMPORTS
# ============================================================

import os

import redis
from fastapi.testclient import TestClient
from sqlalchemy import event

import db.database as db_module


# ============================================================
# AUTH HELPERS
# ============================================================

def register_user(
    client: TestClient,
    email: str,
    password: str = "password123",
):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    return response


def login_user(
    client: TestClient,
    email: str,
    password: str = "password123",
):
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    return response


def get_csrf_token(login_response):
    csrf_token = login_response.cookies.get("csrf_token")

    assert csrf_token is not None

    return csrf_token


# ============================================================
# REGISTRATION
# ============================================================

def test_register_user(client):
    response = register_user(
        client,
        "alice@example.com",
        "secure123",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "alice@example.com"
    assert data["is_active"] is True


def test_register_duplicate_email(client):
    first_response = register_user(
        client,
        "duplicate@test.com",
    )

    assert first_response.status_code == 200

    second_response = register_user(
        client,
        "duplicate@test.com",
    )

    assert second_response.status_code in (400, 409)


def test_register_missing_email(client):
    response = client.post(
        "/auth/register",
        json={
            "password": "password123",
        },
    )

    assert response.status_code == 422


def test_register_missing_password(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "nopassword@test.com",
        },
    )

    assert response.status_code == 422


# ============================================================
# LOGIN
# ============================================================

def test_login_correct_password(client):
    register_response = register_user(
        client,
        "login@test.com",
    )

    assert register_response.status_code == 200

    response = login_user(
        client,
        "login@test.com",
    )

    assert response.status_code == 200

    assert response.cookies.get("access_token") is not None
    assert response.cookies.get("refresh_token") is not None
    assert response.cookies.get("csrf_token") is not None


def test_login_invalid_password(client):
    register_response = register_user(
        client,
        "bob@example.com",
        "correct123",
    )

    assert register_response.status_code == 200

    response = login_user(
        client,
        "bob@example.com",
        "wrongpassword",
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_unknown_user(client):
    response = login_user(
        client,
        "unknown@test.com",
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_missing_password(client):
    register_response = register_user(
        client,
        "missingpass@test.com",
    )

    assert register_response.status_code == 200

    response = client.post(
        "/auth/login",
        data={
            "username": "missingpass@test.com",
        },
    )

    assert response.status_code == 422


def test_login_missing_username(client):
    response = client.post(
        "/auth/login",
        data={
            "password": "password123",
        },
    )

    assert response.status_code == 422


# ============================================================
# REFRESH TOKEN + CSRF
# ============================================================

def test_refresh_token_flow(client):
    register_response = register_user(
        client,
        "ref@example.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "ref@example.com",
        "123",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    refresh_response = client.post(
        "/auth/refresh",
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert refresh_response.status_code == 200

    data = refresh_response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_refresh_without_csrf(client):
    register_response = register_user(
        client,
        "csrf@test.com",
        "password123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "csrf@test.com",
        "password123",
    )

    assert login_response.status_code == 200

    response = client.post("/auth/refresh")

    assert response.status_code == 422


def test_refresh_with_invalid_csrf(client):
    register_response = register_user(
        client,
        "badcsrf@test.com",
        "password123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "badcsrf@test.com",
        "password123",
    )

    assert login_response.status_code == 200

    response = client.post(
        "/auth/refresh",
        headers={
            "X-CSRF-Token": "wrong-token",
        },
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Security error: Invalid CSRF token"
    )


# ============================================================
# TASK AUTHORIZATION
# ============================================================

def test_unauthorized_task_creation(client):
    response = client.post(
        "/tasks/",
        json={
            "title": "Secret task",
            "priority": 1,
        },
    )

    assert response.status_code == 401


def test_tasks_list_requires_authentication(client):
    response = client.get("/tasks/")

    assert response.status_code == 401


def test_admin_tasks_requires_authentication(client):
    response = client.get("/tasks/admin/tasks")

    assert response.status_code == 401


def test_reports_generate_requires_authentication(client):
    response = client.post("/reports/generate")

    assert response.status_code == 401


def test_admin_routes_permissions(client):
    register_response = register_user(
        client,
        "common@test.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "common@test.com",
        "123",
    )

    assert login_response.status_code == 200

    response = client.get("/tasks/admin/tasks")

    assert response.status_code == 403


# ============================================================
# TASK CREATION
# ============================================================

def test_create_task_with_authentication(client):
    register_response = register_user(
        client,
        "createtask@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "createtask@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    response = client.post(
        "/tasks/",
        json={
            "title": "Important task",
            "priority": 5,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["title"] == "Important task"
    assert data["priority"] == 5


def test_create_task_without_csrf(client):
    register_response = register_user(
        client,
        "taskcsrf@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "taskcsrf@test.com",
    )

    assert login_response.status_code == 200

    response = client.post(
        "/tasks/",
        json={
            "title": "CSRF protected task",
            "priority": 1,
        },
    )

    assert response.status_code in (403, 422)


def test_create_task_with_invalid_csrf(client):
    register_response = register_user(
        client,
        "invalidtaskcsrf@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "invalidtaskcsrf@test.com",
    )

    assert login_response.status_code == 200

    response = client.post(
        "/tasks/",
        json={
            "title": "Invalid CSRF task",
            "priority": 1,
        },
        headers={
            "X-CSRF-Token": "invalid-token",
        },
    )

    assert response.status_code == 403


# ============================================================
# TASK LIST
# ============================================================

def test_tasks_list_after_creating_task(client):
    register_response = register_user(
        client,
        "listtask@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "listtask@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "Visible task",
            "priority": 2,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert create_response.status_code == 200

    response = client.get("/tasks/")

    assert response.status_code == 200

    tasks = response.json()

    assert len(tasks) == 1
    assert tasks[0]["title"] == "Visible task"
    assert tasks[0]["priority"] == 2


def test_multiple_tasks_are_returned(client):
    register_response = register_user(
        client,
        "multipletasks@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "multipletasks@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    for index in range(3):
        response = client.post(
            "/tasks/",
            json={
                "title": f"Task {index}",
                "priority": index,
            },
            headers={
                "X-CSRF-Token": csrf_token,
            },
        )

        assert response.status_code == 200

    response = client.get("/tasks/")

    assert response.status_code == 200

    tasks = response.json()

    assert len(tasks) == 3

    assert {task["title"] for task in tasks} == {
        "Task 0",
        "Task 1",
        "Task 2",
    }


# ============================================================
# USER DATA ISOLATION
# ============================================================

def test_users_data_isolation(client):
    register_user1 = register_user(
        client,
        "user1@test.com",
        "123",
    )

    assert register_user1.status_code == 200

    login_user1 = login_user(
        client,
        "user1@test.com",
        "123",
    )

    assert login_user1.status_code == 200

    csrf_user1 = get_csrf_token(login_user1)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "First user's task",
            "priority": 3,
        },
        headers={
            "X-CSRF-Token": csrf_user1,
        },
    )

    assert create_response.status_code == 200

    register_user2 = register_user(
        client,
        "user2@test.com",
        "123",
    )

    assert register_user2.status_code == 200

    login_user2 = login_user(
        client,
        "user2@test.com",
        "123",
    )

    assert login_user2.status_code == 200

    response = client.get("/tasks/")

    assert response.status_code == 200
    assert response.json() == []


def test_task_data_does_not_leak_between_users(client):
    register_owner = register_user(
        client,
        "owner@test.com",
    )

    assert register_owner.status_code == 200

    login_owner = login_user(
        client,
        "owner@test.com",
    )

    assert login_owner.status_code == 200

    owner_csrf = get_csrf_token(login_owner)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "Private task",
            "priority": 10,
        },
        headers={
            "X-CSRF-Token": owner_csrf,
        },
    )

    assert create_response.status_code == 200

    register_other = register_user(
        client,
        "other@test.com",
    )

    assert register_other.status_code == 200

    login_other = login_user(
        client,
        "other@test.com",
    )

    assert login_other.status_code == 200

    response = client.get("/tasks/")

    assert response.status_code == 200
    assert response.json() == []


# ============================================================
# N+1 QUERY REGRESSION
# ============================================================

def test_no_n_plus_one_on_tasks_list(client):
    register_response = register_user(
        client,
        "perf@test.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "perf@test.com",
        "123",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    headers = {
        "X-CSRF-Token": csrf_token,
    }

    for index in range(5):
        response = client.post(
            "/tasks/",
            json={
                "title": f"Task {index}",
                "priority": index,
            },
            headers=headers,
        )

        assert response.status_code == 200

    query_count = 0

    def count_queries(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        nonlocal query_count

        if statement.strip().upper().startswith("SELECT"):
            query_count += 1

    event.listen(
        db_module.engine,
        "before_cursor_execute",
        count_queries,
    )

    try:
        response = client.get(
            "/tasks/",
            headers=headers,
        )

        assert response.status_code == 200
        assert len(response.json()) == 5

        assert query_count <= 2

    finally:
        event.remove(
            db_module.engine,
            "before_cursor_execute",
            count_queries,
        )


# ============================================================
# CELERY / REPORTS
# ============================================================

def test_generate_and_check_report(client):
    register_response = register_user(
        client,
        "report_user@test.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "report_user@test.com",
        "123",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    headers = {
        "X-CSRF-Token": csrf_token,
    }

    response = client.post(
        "/reports/generate",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "task_id" in data

    task_id = data["task_id"]

    status_response = client.get(
        f"/reports/status/{task_id}",
        headers=headers,
    )

    assert status_response.status_code == 200

    status_data = status_response.json()

    assert status_data["task_id"] == task_id
    assert status_data["status"] == "SUCCESS"
    assert status_data["ready"] is True
    assert status_data["result"] is not None

    assert (
        status_data["result"]["user_email"]
        == "report_user@test.com"
    )

    assert (
        status_data["result"]["status"]
        == "completed"
    )


def test_report_status_unknown_task(client):
    register_response = register_user(
        client,
        "report_unknown@example.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "report_unknown@example.com",
    )

    assert login_response.status_code == 200

    response = client.get(
        "/reports/status/nonexistent-task-id"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == "nonexistent-task-id"
    assert data["ready"] is False


# ============================================================
# HEALTH
# ============================================================

def test_health_endpoint_is_available_without_authentication(client):
    response = client.get("/health")

    assert response.status_code == 200


# ============================================================
# REDIS RATE LIMITING
# ============================================================

def test_rate_limit(client):
    responses = []

    for _ in range(21):
        response = client.get("/health")
        responses.append(response.status_code)

    assert responses[:20] == [200] * 20
    assert responses[20] == 429


def test_rate_limit_sets_redis_ttl(client):
    redis_client = redis.Redis.from_url(
        os.environ["REDIS_URL_BROKER"],
        decode_responses=True,
    )

    try:
        response = client.get("/health")

        assert response.status_code == 200

        ttl = redis_client.ttl(
            "ratelimit:ip:testclient"
        )

        assert 0 < ttl <= 60

    finally:
        redis_client.close()