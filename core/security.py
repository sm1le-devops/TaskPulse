import os
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from db.database import get_db
from models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Secret key for signing JWTs (hidden in environment variables .env in real projects)
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN = int(os.getenv("ACCESS_TOKEN", "120"))
REFRESH_TOKEN = int(os.getenv("REFRESH_TOKEN", "604800"))
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))


# 1. Password hashing function
def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")

    hashed_password = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    )

    return hashed_password.decode("utf-8")


def get_current_user(
    request: Request, db: Session = Depends(get_db)
):  # <--- Accepting request
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    # Retrieve access_token directly from the browser's HttpOnly cookie!
    token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception

    try:
        # Decode the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Look up user in the database
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have enough permissions (administrator rights required)",
        )
    return current_user


# 2. Password verification function (compares user input against the database hash)
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# 3. JWT token generation function
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN)
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_csrf_token(request: Request, x_csrf_token: str = Header(...)):
    cookie_csrf = request.cookies.get("csrf_token")

    if not cookie_csrf or cookie_csrf != x_csrf_token:
        raise HTTPException(
            status_code=403, detail="Security error: Invalid CSRF token"
        )


def create_refresh_token() -> str:
    return str(uuid.uuid4())
