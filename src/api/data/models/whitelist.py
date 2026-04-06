from pydantic import BaseModel, Field, field_validator
from .validators import validate_subdomain


class WhitelistEntry(BaseModel):
    """Whitelist entry model equivalent to it's DB record."""
    username: str = Field(..., max_length=50, description="Username of the player")
    subdomain: str = Field(..., min_length=4, max_length=4, description="Server subdomain assigned to the player")

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        return validate_subdomain(v)
