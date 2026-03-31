from dataclasses import dataclass

@dataclass
class AuthContext:
    user_email: str
    user_role: str
    
