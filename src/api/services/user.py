from ..data.models.session import RegisterRequest, RegisterResponse
from ...exceptions.errors import ConflictError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..data.user.manager import SQLUserManager

class UserService:

    def __init__(self, *, users: 'SQLUserManager') -> None:
        self.users = users

    def user_register_public(self, data: RegisterRequest) -> RegisterResponse:
        try:
            self.users.create(data.email, data.password, "user")
        except ConflictError:
            return RegisterResponse(
                status=False,
                message="User already exists",
            )

        return RegisterResponse(
            status=True,
            message="User registered successfully",
        )