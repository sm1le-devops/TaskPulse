import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")


if "sqlite" in SQLALCHEMY_DATABASE_URL:
    connect_args = {"check_same_thread": False}

    if ":memory:" in SQLALCHEMY_DATABASE_URL:
        if "cache=shared" not in SQLALCHEMY_DATABASE_URL:
            SQLALCHEMY_DATABASE_URL += "?cache=shared"
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL, connect_args=connect_args, poolclass=StaticPool
        )
    else:
        engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
