import os

os.environ["SECRET_KEY"] = "test_secret_key_for_pytest_12345"
os.environ["DATABASE_URL"] = "sqlite:///:memory:?cache=shared"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_STORE_EAGER_RESULT"] = "True"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.database as db_module

DATABASE_URL = "sqlite:///:memory:?cache=shared"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

db_module.engine = engine
db_module.SessionLocal = TestingSessionLocal

from fastapi.testclient import TestClient
from db.database import Base, get_db
from main import app
import models.models
import workers.celery_tasks

if hasattr(workers.celery_tasks, "SessionLocal"):
    workers.celery_tasks.SessionLocal = TestingSessionLocal

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def client():
    with TestClient(
        app,
        base_url="https://testserver",
    ) as test_client:
        yield test_client

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "password": "secure123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["is_active"] is True

def test_login_invalid_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "password": "correct123",
        },
    )
    response = client.post(
        "/auth/login",
        data={
            "username": "bob@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_refresh_token_flow(client):
    client.post(
        "/auth/register",
        json={
            "email": "ref@example.com",
            "password": "123",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={
            "username": "ref@example.com",
            "password": "123",
        },
    )
    assert login_res.status_code == 200
    refresh_res = client.post("/auth/refresh")
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens

def test_unauthorized_task_creation(client):
    response = client.post(
        "/tasks/",
        json={
            "title": "Secret task",
            "priority": 1,
        },
    )
    assert response.status_code == 401

def test_users_data_isolation(client):
    client.post(
        "/auth/register",
        json={
            "email": "user1@test.com",
            "password": "123",
        },
    )
    client.post(
        "/auth/login",
        data={
            "username": "user1@test.com",
            "password": "123",
        },
    )
    csrf_cookie = client.cookies.get("csrf_token")
    headers = {
        "X-CSRF-Token": csrf_cookie
    } if csrf_cookie else {}
    response = client.post(
        "/tasks/",
        json={
            "title": "First user's task",
            "priority": 3,
        },
        headers=headers,
    )
    assert response.status_code == 200
    client.post(
        "/auth/register",
        json={
            "email": "user2@test.com",
            "password": "123",
        },
    )
    client.post(
        "/auth/login",
        data={
            "username": "user2@test.com",
            "password": "123",
        },
    )
    csrf_cookie2 = client.cookies.get("csrf_token")
    headers2 = {
        "X-CSRF-Token": csrf_cookie2
    } if csrf_cookie2 else {}
    res = client.get(
        "/tasks/",
        headers=headers2,
    )
    assert res.status_code == 200
    assert res.json() == []

def test_admin_routes_permissions(client):
    client.post(
        "/auth/register",
        json={
            "email": "common@test.com",
            "password": "123",
        },
    )
    client.post(
        "/auth/login",
        data={
            "username": "common@test.com",
            "password": "123",
        },
    )
    res = client.get("/tasks/admin/tasks")
    assert res.status_code == 403

def test_no_n_plus_one_on_tasks_list(client):
    client.post(
        "/auth/register",
        json={
            "email": "perf@test.com",
            "password": "123",
        },
    )
    client.post(
        "/auth/login",
        data={
            "username": "perf@test.com",
            "password": "123",
        },
    )
    csrf_cookie = client.cookies.get("csrf_token")
    headers = {
        "X-CSRF-Token": csrf_cookie
    } if csrf_cookie else {}
    for i in range(5):
        response = client.post(
            "/tasks/",
            json={
                "title": f"Task {i}",
                "priority": i,
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
        engine,
        "before_cursor_execute",
        count_queries,
    )
    try:
        response = client.get(
            "/tasks/",
            headers=headers,
        )
        assert response.status_code == 200
        assert query_count <= 2
    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            count_queries,
        )

def test_generate_and_check_report(client):
    client.post(
        "/auth/register",
        json={
            "email": "report_user@test.com",
            "password": "123",
        },
    )
    client.post(
        "/auth/login",
        data={
            "username": "report_user@test.com",
            "password": "123",
        },
    )
    csrf_cookie = client.cookies.get("csrf_token")
    headers = {
        "X-CSRF-Token": csrf_cookie
    } if csrf_cookie else {}
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