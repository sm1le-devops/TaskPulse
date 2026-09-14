import os

# ============================================================
# TEST ENVIRONMENT
# ============================================================

os.environ["SECRET_KEY"] = "test_secret_key_for_pytest_12345"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["BCRYPT_ROUNDS"] = "4"

os.environ["REDIS_URL_BROKER"] = "redis://localhost:6379/0"

os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_STORE_EAGER_RESULT"] = "True"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"


# ============================================================
# IMPORTS
# ============================================================

from unittest.mock import patch

import pytest
import redis

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.database as db_module
import models.models
import workers.celery_tasks

from db.database import Base, get_db
from main import app


# ============================================================
# SINGLE TEST DATABASE
# ============================================================

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ============================================================
# REPLACE APPLICATION DATABASE
# ============================================================

db_module.engine = engine
db_module.SessionLocal = TestingSessionLocal

if hasattr(workers.celery_tasks, "SessionLocal"):
    workers.celery_tasks.SessionLocal = TestingSessionLocal


def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ============================================================
# DATABASE FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


# ============================================================
# REDIS FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def clean_redis():
    client = redis.Redis.from_url(
        os.environ["REDIS_URL_BROKER"],
        decode_responses=True,
    )

    client.flushdb()

    yield

    client.flushdb()
    client.close()


# ============================================================
# BACKGROUND TASK FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def mock_background_tasks():
    """
    Prevent artificial 5-second welcome email delay
    during tests.
    """
    with patch(
        "routers.auth.send_welcome_email_task.delay"
    ) as mock_email:
        yield mock_email


# ============================================================
# FASTAPI CLIENT
# ============================================================

@pytest.fixture
def client():
    with TestClient(
        app,
        base_url="https://testserver",
    ) as test_client:
        yield test_client