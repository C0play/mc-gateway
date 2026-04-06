from typing import Annotated

from fastapi import Depends
from fastapi import HTTPException, status
from fastapi.security import SecurityScopes

from .context import AuthContext
from .authentication import AuthenticationManager



class AuthorizationManager:
    """
    Class responsible for the authorization of API requests.
    Exposes the require property meant for use with FastAPI Security function. 
    """

    def __init__(self, auth_manager: AuthenticationManager) -> None:
        self.auth_manager = auth_manager


    @property
    def require(self):
        """
        Checks if the user making the request has the required scopes. 
        Does not check ownership of the requested resources.
        """
        def _dependency(
            security_scopes: SecurityScopes,
            auth_context: Annotated[AuthContext, Depends(self.auth_manager.get_auth_context)],
        ) -> AuthContext:
            for scope in security_scopes.scopes:
                if not self.auth_manager.roles.validate(scope, auth_context.user_role):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="action not permitted",
                    )
            
            return auth_context

        return _dependency