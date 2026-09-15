# ============================================================
# IMPORTS
# ============================================================

import os
import uuid
from datetime import timedelta
from unittest.mock import patch

import redis
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import event

import db.database as db_module
from core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)

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
# SECURITY UNIT TESTS
# ============================================================


def test_password_hash_and_verify():
    password = "SuperSecret123!"

    hashed_password = get_password_hash(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password) is True
    assert verify_password("WrongPassword", hashed_password) is False


def test_create_access_token():
    token = create_access_token(
        {"sub": "security@test.com"},
        expires_delta=timedelta(minutes=5),
    )

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    assert payload["sub"] == "security@test.com"
    assert "exp" in payload


def test_create_refresh_token():
    token = create_refresh_token()

    assert isinstance(token, str)
    assert len(token) == 36
    assert str(uuid.UUID(token)) == token


def test_invalid_access_token_returns_401(client):
    client.cookies.set(
        "access_token",
        "invalid.jwt.token",
    )

    response = client.get("/tasks/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_access_token_without_subject_returns_401(client):
    token = jwt.encode(
        {"some_field": "value"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    client.cookies.set(
        "access_token",
        token,
    )

    response = client.get("/tasks/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


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
    assert response.json()["detail"] == ("Security error: Invalid CSRF token")


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


def test_get_task_by_id(client):
    register_response = register_user(
        client,
        "gettask@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "gettask@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "Find me",
            "priority": 7,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["id"]

    response = client.get(f"/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["id"] == task_id
    assert response.json()["title"] == "Find me"


def test_get_nonexistent_task(client):
    register_response = register_user(
        client,
        "missingtask@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "missingtask@test.com",
    )

    assert login_response.status_code == 200

    response = client.get("/tasks/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_tasks_filter_by_priority(client):
    register_response = register_user(
        client,
        "priorityfilter@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "priorityfilter@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    for priority in [1, 5, 5]:
        response = client.post(
            "/tasks/",
            json={
                "title": f"Priority {priority}",
                "priority": priority,
            },
            headers={
                "X-CSRF-Token": csrf_token,
            },
        )

        assert response.status_code == 200

    response = client.get("/tasks/?priority=5")

    assert response.status_code == 200

    tasks = response.json()

    assert len(tasks) == 2
    assert all(task["priority"] == 5 for task in tasks)


def test_tasks_filter_by_completed(client):
    register_response = register_user(
        client,
        "completedfilter@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "completedfilter@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "Completed task",
            "priority": 1,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["id"]

    update_response = client.put(
        f"/tasks/{task_id}",
        json={
            "completed": True,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert update_response.status_code == 200

    response = client.get("/tasks/?completed=true")

    assert response.status_code == 200

    tasks = response.json()

    assert len(tasks) == 1
    assert tasks[0]["completed"] is True


def test_tasks_list_cache_hit(client):
    register_response = register_user(
        client,
        "cachehit@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "cachehit@test.com",
    )

    assert login_response.status_code == 200

    with patch(
        "routers.tasks.get_cached_tasks",
        return_value=[
            {
                "id": 999,
                "title": "Cached task",
                "completed": False,
                "priority": 10,
            }
        ],
    ):
        response = client.get("/tasks/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == 999
    assert data[0]["title"] == "Cached task"


# ============================================================
# UPDATE / DELETE
# ============================================================


def test_delete_nonexistent_task(client):
    register_response = register_user(
        client,
        "delete404@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "delete404@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    response = client.delete(
        "/tasks/99999",
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task(client):
    register_response = register_user(
        client,
        "updatetask@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "updatetask@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "Old title",
            "priority": 1,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={
            "title": "New title",
            "priority": 10,
            "completed": True,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == task_id
    assert data["title"] == "New title"
    assert data["priority"] == 10
    assert data["completed"] is True


def test_update_nonexistent_task(client):
    register_response = register_user(
        client,
        "update404@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "update404@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    response = client.put(
        "/tasks/99999",
        json={
            "title": "Does not exist",
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_delete_task(client):
    register_response = register_user(
        client,
        "deletetask@test.com",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "deletetask@test.com",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    create_response = client.post(
        "/tasks/",
        json={
            "title": "Delete me",
            "priority": 1,
        },
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["id"]

    response = client.delete(
        f"/tasks/{task_id}",
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == (
        f"Task with id {task_id} successfully deleted"
    )

    get_response = client.get(f"/tasks/{task_id}")

    assert get_response.status_code == 404


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
        "Idempotency-Key": "report-test-flow-123",
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

    assert status_data["result"]["user_email"] == ("report_user@test.com")

    assert status_data["result"]["status"] == "completed"


def test_report_idempotency_same_key_returns_same_task(client):
    register_response = register_user(
        client,
        "idempotency@test.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "idempotency@test.com",
        "123",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Idempotency-Key": "report-test-123",
    }

    with patch(
        "routers.reports.generate_user_report_task.apply_async"
    ) as mock_apply_async:
        first_response = client.post(
            "/reports/generate",
            headers=headers,
        )

        second_response = client.post(
            "/reports/generate",
            headers=headers,
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_data = first_response.json()
    second_data = second_response.json()

    assert first_data["task_id"] == second_data["task_id"]

    assert first_data["idempotent"] is False
    assert second_data["idempotent"] is True

    assert mock_apply_async.call_count == 1


def test_report_idempotency_different_keys_create_different_tasks(client):
    register_response = register_user(
        client,
        "different-keys@test.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "different-keys@test.com",
        "123",
    )

    assert login_response.status_code == 200

    csrf_token = get_csrf_token(login_response)

    with patch(
        "routers.reports.generate_user_report_task.apply_async"
    ) as mock_apply_async:
        response_one = client.post(
            "/reports/generate",
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": "key-1",
            },
        )

        response_two = client.post(
            "/reports/generate",
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": "key-2",
            },
        )

    assert response_one.status_code == 200
    assert response_two.status_code == 200

    data_one = response_one.json()
    data_two = response_two.json()

    assert data_one["task_id"] != data_two["task_id"]

    assert data_one["idempotent"] is False
    assert data_two["idempotent"] is False

    assert mock_apply_async.call_count == 2


def test_report_generation_requires_idempotency_key(client):
    register_response = register_user(
        client,
        "missing-idempotency@test.com",
        "123",
    )

    assert register_response.status_code == 200

    login_response = login_user(
        client,
        "missing-idempotency@test.com",
        "123",
    )

    assert login_response.status_code == 200

    response = client.post("/reports/generate")

    assert response.status_code == 400

    assert response.json()["detail"] == ("Idempotency-Key header is required")


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

    response = client.get("/reports/status/nonexistent-task-id")

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

        ttl = redis_client.ttl("ratelimit:ip:testclient")

        assert 0 < ttl <= 60

    finally:
        redis_client.close()
