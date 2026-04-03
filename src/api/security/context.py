from dataclasses import dataclass
from uuid import UUID



@dataclass
class AuthContext:
    user_email: str
    user_role: str
    session_id: UUID | None
    api_key: str | None