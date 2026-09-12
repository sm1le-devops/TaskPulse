from db.database import Base
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class Task(Base):
  """Task model representing a to-do item belonging to a specific user."""

  __tablename__ = "tasks"

  id = Column(Integer, primary_key=True, index=True)
  title = Column(String)
  completed = Column(Boolean, default=False)
  priority = Column(Integer)

  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class User(Base):
  """User model representing registered system accounts and their roles."""

  __tablename__ = "users"

  id = Column(Integer, primary_key=True, index=True)
  email = Column(String, unique=True, index=True, nullable=False)
  hashed_password = Column(String, nullable=False)
  is_active = Column(Boolean, default=True)

  is_admin = Column(Boolean, default=False)

  refresh_tokens = relationship(
      "RefreshToken", back_populates="user", cascade="all, delete"
  )


class RefreshToken(Base):
  """Refresh token model for storing active session tokens tied to users."""

  __tablename__ = "refresh_tokens"

  id = Column(Integer, primary_key=True, index=True)
  token = Column(String, unique=True, index=True, nullable=False)
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

  user = relationship("User", back_populates="refresh_tokens")