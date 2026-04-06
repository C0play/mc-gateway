from dataclasses import dataclass
from uuid import UUID

from .roles import Role


@dataclass
class AuthContext:
    user_email: str
    user_role: Role
    session_id: UUID | None
    api_key: str | None