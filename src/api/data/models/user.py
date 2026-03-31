from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254, description="User email")
    password: str = Field(..., min_length=8, max_length=256, description="Plaintext password")


class RegisterResponse(BaseModel):
    email: str = Field(..., description="Registered user email")
    api_key: str = Field(..., description="Newly created API key")
