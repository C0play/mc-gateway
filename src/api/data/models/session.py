from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserCredentials(BaseModel):
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., description="User password (plain text).")


class RegisterRequest(UserCredentials):
    pass


class RegisterResponse(BaseModel):
    status : bool = Field(..., description="Whether registering was successful.")
    message: str = Field(..., description="Success/Failure message.")


class LoginRequest(UserCredentials):
    pass


class Session(BaseModel):
    """Session model equivalent to it's DB record."""
    user_email: EmailStr = Field(..., description="User email address.")
    access_token: str = Field(..., description="Bearer token used to authenticate requests.")
    created_at: datetime = Field(..., description="Session creation date and time")
    valid_until: datetime = Field(..., description="Session expiration date and time")


class SessionResponse(Session):
    """Session response model for OAuth2."""
    token_type: str = Field("bearer", description="Token type according to OAuth2.")