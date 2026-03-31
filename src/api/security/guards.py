from dataclasses import dataclass
from typing import Callable

from .pipeline import AccessPipeline, AuthMode
from ..data.user.roles import Permission


@dataclass(frozen=True)
class AccessGuards:
    require_manage_whitelists: Callable
    require_manage_containers: Callable
    require_manage_hosts: Callable
    require_view_status: Callable
    require_stop_server: Callable
    require_session: Callable
    require_user_manage_own_apikeys: Callable
    require_user_manage_own_containers: Callable


def build_access_guards(access: AccessPipeline) -> AccessGuards:
    return AccessGuards(
        require_manage_whitelists=access.guard(
            auth_modes=(AuthMode.API_KEY, AuthMode.BEARER),
            permissions=(Permission.whitelist_manage_all,),
        ),
        require_manage_containers=access.guard(
            auth_modes=(AuthMode.API_KEY, AuthMode.BEARER),
            permissions=(Permission.container_manage_all,),
        ),
        require_manage_hosts=access.guard(
            auth_modes=(AuthMode.API_KEY, AuthMode.BEARER),
            permissions=(Permission.host_manage_all,),
        ),
        require_view_status=access.guard(
            auth_modes=(AuthMode.API_KEY, AuthMode.BEARER),
            permissions=(Permission.status_get,),
        ),
        require_stop_server=access.guard(
            auth_modes=(AuthMode.API_KEY, AuthMode.BEARER),
            permissions=(Permission.server_shutdown,),
        ),
        require_session=access.guard(
            auth_modes=(AuthMode.BEARER,),
        ),
        require_user_manage_own_apikeys=access.guard(
            auth_modes=(AuthMode.BEARER,),
            permissions=(Permission.api_key_manage_all,),
            ownership_validator=access.key_ownership_validator(),
        ),
        require_user_manage_own_containers=access.guard(
            auth_modes=(AuthMode.BEARER,),
            permissions=(Permission.container_manage_own,),
            ownership_validator=access.container_ownership_validator(),
        ),
    )