from pydantic import BaseModel, ConfigDict, EmailStr


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str
    priority: int


class LoginResponse(BaseModel):
    """Schema for the login response containing authentication details."""

    message: str
    csrf_token: str
    token_type: str = "bearer"


class TaskResponse(BaseModel):
    """Schema for returning task data to the client."""

    id: int
    title: str
    completed: bool
    priority: int

    model_config = ConfigDict(from_attributes=True)


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""

    title: str | None = None
    priority: int | None = None
    completed: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Schema for user registration input data."""

    email: EmailStr  # Pydantic will validate that this is a valid email
    password: str


# Schema for the response (to avoid exposing the password hash)
class UserResponse(BaseModel):
    """Schema for public user profile responses."""

    id: int
    email: str
    is_active: bool
    is_admin: bool | None = False

    model_config = ConfigDict(from_attributes=True)


# Schema for the token returned upon login
class Token(BaseModel):
    """Schema representing an access token."""

    access_token: str
    token_type: str


# Schema for the token pair upon login
class TokenResponse(BaseModel):
    """Schema representing a token response with default bearer type."""

    access_token: str
    token_type: str = "bearer"


# Schema used by the client to request an access token refresh
class RefreshRequest(BaseModel):
    """Schema for token refresh requests."""

    refresh_token: str
