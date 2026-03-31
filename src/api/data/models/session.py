from pydantic import BaseModel, Field, EmailStr


class UserID(BaseModel):
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., description="User password (plain text).")


class RegisterRequest(UserID):
    pass


class RegisterResponse(BaseModel):
    status : bool = Field(..., description="Whether registering was successful.")
    message: str = Field(..., description="Success/Failure message.")


class LoginRequest(UserID):
    pass


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="Bearer token used to authenticate requests.")
    token_type: str = Field("bearer", description="Token type according to OAuth2.")