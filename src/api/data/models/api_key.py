from datetime import datetime

from pydantic import BaseModel, Field


class ApiKey(BaseModel): 
    active : bool = Field(..., description="Flag whether the keys is active.")
    name: str = Field(..., description="Key name.")
    created_at : datetime = Field(..., description="Date of creation.")
    last_used_at : datetime = Field(..., description="Date of last user.")
    revoked_at : datetime | None = Field(..., description="Date of deletion.")
    user : str = Field(..., description="Owner's email address.")