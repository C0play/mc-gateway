from enum import IntEnum, auto
from ...exceptions.errors import NotFoundError


class Permission(IntEnum):
    # all CRUD endpoints
    host_manage_all         = auto()
    container_manage_all    = auto()
    whitelist_manage_all    = auto()
    api_keys_manage_all     = auto()
    users_manage_all        = auto()
    # all _R__ endpoints (monitoring etc.)
    host_get_all            = auto()
    container_get_all       = auto()
    whitelist_get_all       = auto()
    api_key_get_all         = auto()
    user_get_all            = auto()
    status_get              = auto()
    # all _RU_ endpoints restricted to user's own data
    container_manage_own    = auto()
    whitelist_manage_own    = auto()
    api_keys_manage_own     = auto()
    user_manage_own         = auto()
    # other
    server_shutdown         = auto()



class PermissionRepository:

    def __init__(self) -> None:
        self.permissions = {}

    
    def add(self, permission: Permission) -> 'PermissionRepository':
        self.permissions[permission.name] = (1 << len(self.permissions))
        return self
    

    def get(self, permission: Permission) -> int:
        if permission.name not in self.permissions:
            raise NotFoundError(f"permission {permission.name} does not exist")
        return self.permissions[permission.name]


    def combine(self, permissions: list[Permission]) -> int:
        res = 0
        for perm in permissions:
            if perm.name not in self.permissions:
                raise NotFoundError(f"permission {perm.name} does not exist")
            res = res | self.permissions[perm.name]

        return res
            
        

class RoleRepository:

    def __init__(self) -> None:
        
        self.perms = PermissionRepository()

        for permission in Permission:
            self.perms.add(permission)

        self.roles = {
            "superadmin": self.perms.combine([
                Permission.host_manage_all,
                Permission.container_manage_all,
                Permission.whitelist_manage_all,
                Permission.api_keys_manage_all,
                Permission.users_manage_all,
                Permission.status_get,
                Permission.server_shutdown,
            ]),
            "user": self.perms.combine([
                Permission.api_keys_manage_own,
                Permission.container_manage_own,
                Permission.user_manage_own,
                Permission.whitelist_manage_own,
            ])
        }


    def get(self, name: str) -> int:
        if name not in self.roles:
            raise NotFoundError(f"role {name} does not exist")
        
        return self.roles[name]
    

    def validate(self, permission: Permission, role: str) -> bool:
        permission_val = self.perms.get(permission)
        role_val = self.get(role)

        return (permission_val & role_val) > 0