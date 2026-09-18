from dataclasses import dataclass
from enum import StrEnum, auto

from ...exceptions.errors import NotFoundError


class Permission(StrEnum):
    """Enum defining all permissions a user can have."""

    description: str

    def __new__(cls, scope: str | int, description: str):
        scope_str = str(scope)
        obj = str.__new__(cls, scope_str)
        obj._value_ = scope_str
        obj.description = description
        return obj

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.replace("_", ":")

    def __str__(self) -> str:
        return self.value

    # Hosts
    host_create = auto(), "Register a host machine"
    host_read = auto(), "Fetch host machine data"
    host_update = auto(), "Update a host machine"
    host_delete = auto(), "Delete a host machine"
    host_kick = auto(), "Kick all players from all containers running on a host"

    # Containers
    container_create = auto(), "Create a container "
    container_read = auto(), "Fetch container data configuration"
    container_update = auto(), "Update a container"
    container_delete = auto(), "Delete a container"
    container_kick = auto(), "Kick all players from a container"

    # Whitelists
    whitelist_create = auto(), "Add a player to a containers whitelist"
    whitelist_read = auto(), "Fetch a container's whitelist"
    whitelist_delete = auto(), "Remove a player from a containers whitelist"
    whitelist_kick = auto(), "Kick a player from a container"

    # Api keys
    api_key_create = auto(), "Create an api key"
    api_key_read = auto(), "Fetch api key data"
    api_key_revoke = auto(), "Revoke an api key"
    api_key_delete = auto(), "Delete an api key permanently"

    # Users
    user_read = auto(), "Read user data"
    user_update_role = auto(), "Update user's role"
    user_view_roles = auto(), "Fetch all roles"
    user_delete = auto(), "Delete a user"

    # Other
    system_status_read = auto(), "Fetch active sessions, hosts and containers counts"
    system_manage = auto(), "Issue shutdown commands"


class PermissionRepository:
    """Class storing all permissions as bit masks."""

    def __init__(self) -> None:
        self.permissions: dict[str, int] = {}

    def add(self, permission: Permission) -> "PermissionRepository":
        """Adds a new permission <-> bitmask mapping."""
        self.permissions[permission] = 1 << len(self.permissions)
        return self

    def get(self, permission: Permission) -> int:
        """Retrievs a permission's bitmask."""
        if permission not in self.permissions:
            raise NotFoundError(f"permission {permission} does not exist")
        return self.permissions[permission]

    def combine(self, permissions: list[Permission | str]) -> int:
        """Combines multiple permissions into a single bitmask."""
        res = 0
        for perm in permissions:
            if perm not in self.permissions:
                raise NotFoundError(f"permission {perm} does not exist")
            res = res | self.permissions[perm]

        return res


@dataclass(frozen=True)
class Role:
    name: str
    permissions: int
    requires_ownership: bool


class RoleRepository:
    """Class storing roles as aliases for permission sets."""

    def __init__(self) -> None:

        self.perms = PermissionRepository()

        for permission in Permission:
            self.perms.add(permission)

        roles = [
            Role(
                name="admin",
                permissions=self.perms.combine([p for p in Permission]),
                requires_ownership=False,
            )
        ]

        self.roles: dict[str, Role] = {role.name: role for role in roles}

    def get(self, name: str) -> Role:
        """
        Fetches a Role object based on the provided name.

        Args:
            name: The name of the role.

        Returns:
            Role: Role object.

        Raises:
            NotFoundError: If the name does not correspond to a registered role.

        """
        if name not in self.roles:
            raise NotFoundError(f"role {name} does not exist")

        return self.roles[name]

    def get_all(self) -> list[Role]:
        return [role for role in self.roles.values()]

    def validate(self, requested_scope: str, role: Role) -> bool:
        try:
            permission = Permission(requested_scope)
        except ValueError:
            return False

        permission_val = self.perms.get(permission)

        return (permission_val & role.permissions) > 0


SCOPES: dict[str, str] = {p.value: p.description for p in Permission}
