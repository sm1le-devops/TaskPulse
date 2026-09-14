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

# 1. Сначала создаем тестовый движок и патчим db.database ДО импорта app и celery
import db.database as db_module

DATABASE_URL = "sqlite:///:memory:?cache=shared"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

# Переопределяем движок и сессию в модуле базы данных
db_module.engine = engine
db_module.SessionLocal = TestingSessionLocal

# Теперь безопасно импортируем приложение и задачи
from fastapi.testclient import TestClient
from db.database import Base, get_db
from main import app
import models.models
import workers.celery_tasks

# Принудительно подменяем SessionLocal внутри модуля Celery-задач, если он уже успел импортироваться
if hasattr(workers.celery_tasks, "SessionLocal"):
    workers.celery_tasks.SessionLocal = TestingSessionLocal

def override_get_db():
  try:
    db = TestingSessionLocal()
    yield db
  finally:
    db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app, base_url="https://testserver")

@pytest.fixture(autouse=True)
def setup_database():
  Base.metadata.create_all(bind=engine)
  yield
  Base.metadata.drop_all(bind=engine)

# ==========================================
# BLOCK 1: AUTHENTICATION AND REFRESH TESTS
# ==========================================


def test_register_user():
  response = client.post(
      "/auth/register", json={"email": "alice@example.com", "password": "secure123"}
  )
  assert response.status_code == 200
  data = response.json()
  assert data["email"] == "alice@example.com"
  assert data["is_active"] == True


def test_login_invalid_password():
  client.post(
      "/auth/register", json={"email": "bob@example.com", "password": "correct123"}
  )
  # Try to log in with an incorrect password
  response = client.post(
      "/auth/login", data={"username": "bob@example.com", "password": "wrongpassword"}
  )
  assert response.status_code == 401
  assert response.json()["detail"] == "Incorrect email or password"


def test_refresh_token_flow():
  # Register and login to get refresh token via cookies
  client.post(
      "/auth/register", json={"email": "ref@example.com", "password": "123"}
  )
  login_res = client.post(
      "/auth/login", data={"username": "ref@example.com", "password": "123"}
  )
  assert login_res.status_code == 200
  
  # Verify that cookies are set in client and test refresh
  # Request to update access_token through /auth/refresh (sending cookies)
  refresh_res = client.post("/auth/refresh")
  assert refresh_res.status_code == 200
  new_tokens = refresh_res.json()
  assert "access_token" in new_tokens


# ==========================================
# BLOCK 2: TASKS AND USER ISOLATION TESTS
# ==========================================


def test_unauthorized_task_creation():
  response = client.post(
      "/tasks/", json={"title": "Secret task", "priority": 1}
  )
  assert response.status_code == 401


def test_users_data_isolation():
  # Create User 1 and their task
  client.post(
      "/auth/register", json={"email": "user1@test.com", "password": "123"}
  )
  client.post(
      "/auth/login", data={"username": "user1@test.com", "password": "123"}
  )
  # CSRF token is automatically handled or passed via cookies/headers in test client, 
  # assuming client stores cookies automatically across requests.
  csrf_cookie = client.cookies.get("csrf_token")
  headers = {"X-CSRF-Token": csrf_cookie} if csrf_cookie else {}

  client.post(
      "/tasks/",
      json={"title": "First user's task", "priority": 3},
      headers=headers,
  )

  # Create User 2
  client.post(
      "/auth/register", json={"email": "user2@test.com", "password": "123"}
  )
  client.post(
      "/auth/login", data={"username": "user2@test.com", "password": "123"}
  )
  csrf_cookie2 = client.cookies.get("csrf_token")
  headers2 = {"X-CSRF-Token": csrf_cookie2} if csrf_cookie2 else {}

  # User 2 requests their task list — they should NOT see User 1's tasks
  res = client.get("/tasks/", headers=headers2)
  assert res.status_code == 200
  assert res.json() == []  # List must be empty!


# ==========================================
# BLOCK 3: ADMINISTRATOR PERMISSIONS TESTS
# ==========================================


def test_admin_routes_permissions():
  # Register a regular user
  client.post(
      "/auth/register", json={"email": "common@test.com", "password": "123"}
  )
  client.post(
      "/auth/login", data={"username": "common@test.com", "password": "123"}
  )

  # Regular user hits admin endpoint -> should receive 403 Forbidden
  res = client.get("/tasks/admin/tasks")
  assert res.status_code == 403


# ==========================================
# BLOCK 4: N+1 PROBLEM TEST
# ==========================================


def test_no_n_plus_one_on_tasks_list():
    client.post(
        "/auth/register", json={"email": "perf@test.com", "password": "123"}
    )
    client.post(
        "/auth/login", data={"username": "perf@test.com", "password": "123"}
    )
    csrf_cookie = client.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_cookie} if csrf_cookie else {}

    for i in range(5):
        response = client.post(
            "/tasks/",
            json={"title": f"Task {i}", "priority": i},
            headers=headers,
        )
        assert response.status_code == 200

    query_count = 0

    @event.listens_for(engine, "before_cursor_execute")
    def count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if statement.strip().startswith("SELECT"):
            query_count += 1

    response = client.get("/tasks/", headers=headers)
    assert response.status_code == 200
    assert query_count <= 2
    
# ==========================================
# BLOCK 5: BACKGROUND REPORTS TESTS
# ==========================================

def test_generate_and_check_report():
    # Register and login user
    client.post(
        "/auth/register", json={"email": "report_user@test.com", "password": "123"}
    )
    client.post(
        "/auth/login", data={"username": "report_user@test.com", "password": "123"}
    )
    csrf_cookie = client.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf_cookie} if csrf_cookie else {}

    # Trigger report generation
    response = client.post("/reports/generate", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Check that task_id is returned
    assert "task_id" in data
    task_id = data["task_id"]

    # Check report status (due to task_always_eager=True, it should be completed instantly)
    status_response = client.get(f"/reports/status/{task_id}", headers=headers)
    assert status_response.status_code == 200
    status_data = status_response.json()
    
    assert status_data["status"] == "completed"
    assert status_data["user_email"] == "report_user@test.com"