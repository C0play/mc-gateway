from dataclasses import dataclass
from typing import Literal
from uuid import UUID

@dataclass
class AuthContext:
    user_email: str
    user_role: str
    session_id: UUID