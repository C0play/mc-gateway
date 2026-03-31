from typing import Annotated

from fastapi import APIRouter, Depends

from ..models.response import ListResponse, MessageResponse
from ..security import AccessContext
from ..services.api_key import ApiKeyService
from ..services.session import SessionService
from .utils import handle_errors


def build_me_router(
    session_service: SessionService,
    api_key_service: ApiKeyService,
    require_session,
    require_user_manage_own_apikeys,
) -> APIRouter:
    router = APIRouter(
        prefix="/me",
        dependencies=[Depends(require_session)],
    )

    apikey_router = APIRouter(
        prefix="/apikey",
        tags=["user: api keys"],
        dependencies=[Depends(require_user_manage_own_apikeys)],
    )

    @router.get("/session", response_model=MessageResponse, tags=["sessions"])
    @handle_errors
    def session_get_own(auth: Annotated[AccessContext, Depends(require_session)]):
        return session_service.session_get_own(auth.email)

    @router.post("/logout", response_model=MessageResponse, tags=["sessions"])
    @handle_errors
    def session_revoke_own(auth: Annotated[AccessContext, Depends(require_session)]):
        return session_service.session_revoke_own(auth.session_id)

    @router.get("/apikey/list", response_model=ListResponse, tags=["user: api keys"])
    @handle_errors
    def api_key_list_own(auth: Annotated[AccessContext, Depends(require_session)], name: str | None = None):
        return api_key_service.api_key_list_own(auth.email, name)

    @apikey_router.post("/create", response_model=MessageResponse)
    @handle_errors
    def api_key_create_own(auth: Annotated[AccessContext, Depends(require_session)]):
        return api_key_service.api_key_create_own(auth.email)

    @apikey_router.delete("/revoke/{name}", response_model=MessageResponse)
    @handle_errors
    def api_key_revoke_own(name: str, auth: Annotated[AccessContext, Depends(require_session)]):
        return api_key_service.api_key_revoke_own(auth.email, name)

    router.include_router(apikey_router)
    return router
