from typing import (
    Annotated,
)
from fastapi import (
    Depends
)

from .context import AuthContext
from .authentication import AuthenticationManager
from .roles import PermissionRepository, RoleRepository, Permission
from ...exceptions import ForbiddenError


class AuthorizationManager:

    def __init__(
        self,
        roles: RoleRepository,
        permissions: PermissionRepository,
        auth_manager: AuthenticationManager,
    ) -> None:
        self.roles = roles
        self.permissions = permissions
        self.auth_manager = auth_manager


    def require(self, required_permission: Permission):
        def _dependency(
            auth_context: Annotated[AuthContext, Depends(self.auth_manager.get_auth_context)],
        ) -> None:
            if not self.roles.validate(required_permission, auth_context.user_role):
                raise ForbiddenError("action not permitted")
        
        return _dependency


    def require_any(self, *required_permissions: Permission):
        def _dependency(
            auth_context: Annotated[AuthContext, Depends(self.auth_manager.get_auth_context)],
        ) -> AuthContext:
            for permission in required_permissions:
                if self.roles.validate(permission, auth_context.user_role):
                    return auth_context
            raise ForbiddenError("action not permitted")

        return _dependency