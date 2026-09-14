from workers.celery_tasks import send_welcome_email_task
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request
from fastapi import Response
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordRequestForm
from core.logger import logger
from core.security import get_current_user
from models.models import RefreshToken, User
from schemas.schemas import (
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from core.security import (
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_csrf_token,
)
from sqlalchemy.orm import Session
import secrets

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
  existing_user = db.query(User).filter(User.email == user_data.email).first()
  if existing_user:
    raise HTTPException(status_code=400, detail="Email is already taken")

  hashed_pass = get_password_hash(user_data.password)
  new_user = User(email=user_data.email, hashed_password=hashed_pass)

  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  logger.info(f"New user registered: {new_user.email}")

  send_welcome_email_task.delay(new_user.email)

  return new_user


@router.post("/login", response_model=LoginResponse)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),  # <--- Using form instead of UserCreate
    db: Session = Depends(get_db),
):
  # form_data.username — contains what the user entered in the "username" field in Swagger (in our case, email)
  # form_data.password — entered password

  user = db.query(User).filter(User.email == form_data.username).first()

  if not user or not verify_password(form_data.password, user.hashed_password):
    logger.warning("Unsuccessful login")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
    )
  logger.info(f"Successful login from user {user.email}")
  # 1. Generate short-lived Access Token
  access_token = create_access_token(data={"sub": user.email})
  refresh_token_str = create_refresh_token()

  csrf_token = secrets.token_hex(32)

  # 3. Save Refresh Token to database (linked to user)
  db_token = RefreshToken(token=refresh_token_str, user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN))
  db.add(db_token)
  db.commit()

  response.set_cookie(
      key="access_token",
      value=access_token,
      httponly=True,
      secure=True,  
      samesite="Lax",
      path="/",
      max_age=ACCESS_TOKEN * 60,
  )

  response.set_cookie(
      key="csrf_token",
      value=csrf_token,
      httponly=False,  
      secure=True,
      samesite="Lax",
      path="/",
  )
  response.set_cookie(
      key="refresh_token",
      value=refresh_token_str,
      httponly=True,  # XSS protection (JS won't be able to steal it)
      secure=True,  
      samesite="Lax",
      path="/",  
      max_age=REFRESH_TOKEN,  
  )

  return {
      "message": "Successful login",
      "csrf_token": csrf_token,
      "token_type": "bearer",
  }


# Access token refresh endpoint
@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    request: Request, response: Response, db: Session = Depends(get_db), _: None = Depends(verify_csrf_token)
):
  # 1. Retrieve refresh_token directly from browser HttpOnly cookies
  refresh_token_val = request.cookies.get("refresh_token")

  if not refresh_token_val:
    logger.warning("Refresh attempt without refresh token in cookies")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token is missing",
    )

  # 2. Look up this refresh token in the database
  db_token = (
      db.query(RefreshToken)
      .filter(RefreshToken.token == refresh_token_val)
      .first()
  )

  if not db_token:
    logger.warning("Invalid refresh token")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )

  expires_at = db_token.expires_at

  if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)

  if expires_at <= datetime.now(timezone.utc):
    db.delete(db_token)
    db.commit()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token has expired",
    )
    
  # 3. Identify the user who owns this token
  user = db.query(User).filter(User.id == db_token.user_id).first()
  if not user:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User not found",
    )

  # 4. Rotation: delete the old refresh token from the database
  db.delete(db_token)
  db.commit()

  # 5. Issue a new pair of tokens
  new_access_token = create_access_token(data={"sub": user.email})
  new_refresh_token = create_refresh_token()

  new_db_token = RefreshToken(
    token=new_refresh_token,
    user_id=user.id,
    expires_at=datetime.now(timezone.utc)
    + timedelta(seconds=REFRESH_TOKEN),
    )
  db.add(new_db_token)
  db.commit()

  response.set_cookie(
      key="access_token",
      value=new_access_token,
      httponly=True,
      secure=True,
      samesite="Lax",
      path="/",
      max_age=ACCESS_TOKEN * 60,
  )
  response.set_cookie(
      key="refresh_token",
      value=new_refresh_token,
      httponly=True,
      secure=True,
      samesite="Lax",
      path="/",
      max_age=REFRESH_TOKEN,
  )

  logger.info(f"New token pair successfully issued for user {user.email}")

  return {
      "access_token": new_access_token,
      "token_type": "bearer",
  }
  
@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Endpoint to retrieve the profile of the currently logged-in user."""

    return current_user

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    refresh_token_val = request.cookies.get("refresh_token")

    if refresh_token_val:
        db_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.token == refresh_token_val)
            .first()
        )

        if db_token:
            db.delete(db_token)
            db.commit()
            
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")

    return {"message": "Successfully logged out"}