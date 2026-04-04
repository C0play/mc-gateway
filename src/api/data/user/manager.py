from abc import ABC, abstractmethod

from .repository import BaseUserRepository, SQLUserRepository
from ...security.roles import RoleRepository, Permission
from ..models.user import User
from ..mappers.user import user_from_record


from ....utils.logger import logger
from ....exceptions.errors import NotFoundError



class BaseUserManager(ABC):

    def __init__(self, 
            user_repository: BaseUserRepository,
            role_manager: RoleRepository,
        ) -> None:
        self.users = user_repository
        self.roles = role_manager


    @abstractmethod
    def create(self, user_email: str, password: str, role: str) -> User:
        """
        Creates a new User. 

        Args:
            user_email: The users's email.
            password: Plain text password set by the user.
            role: Role assigned to the user.

        Returns:
            user: User model instance.

        Raises:
            ConflictError: If the user with the specified email already exists.
        """
        ...


    @abstractmethod
    def read(self, **filters) -> list[User]:
        """
        Retrieves User records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[User]: Matching User model instances.
        """
        ...


    @abstractmethod
    def validate_permission(self, user_email: str, permission: Permission) -> bool:
        """
        Validates the provided permission name against the user's role.

        Args:
            user_email: The users's email.
            permission_name: Name of the permission required to execute a request.

        Returns:
            bool: True if the user has the permissions required for the request, False otherwise.
        """

    @abstractmethod
    def validate_password(self, user_email: str, password: str) -> bool:
        """
        Validates user credentials.

        Args:
            user_email: The users's email.
            password: Plain text password set by the user.

        Returns:
            bool: True if the user has the correct credentials, False otherwise.
        """
        ...

    @abstractmethod
    def update(self, user_email: str, **fields) -> User:
        """
        Update a User.

        Args:
            user_email: The email of the User to update.
            **fields: Key value pair of field names and new values.

        Raises:
            NotFoundError: If the User does not exist.
        """
        ...

    @abstractmethod
    def delete(self, user_email: str,) -> User:
        """
        Deletes a User.

        Args:
            user_email: The email of the User to remove.

        Raises:
            NotFoundError: If the User does not exist.
        """
        ...



class SQLUserManager(BaseUserManager):

    def __init__(self,
        user_repository: SQLUserRepository,
        role_manager: RoleRepository,
    ) -> None:
        super().__init__(user_repository, role_manager)


    def create(self, user_email: str, password: str, role: str) -> User:
        user = self.users.create(user_email, password, role)
        return user_from_record(user)


    def read(self, **filters) -> list[User]:
        records = self.users.read(**filters)
        return [user_from_record(r) for r in records]

    def validate_permission(self, user_email: str, permission: Permission) -> bool:
        users = self.users.read(email=user_email)

        if not users:
            raise NotFoundError(f"user {user_email} does not exist")
        user = users[0]

        if not self.roles.validate(permission, str(user.role)):
            logger.info(f"user {user.email}({user.role}) does not have the permission '{permission}'")
            return False
        
        return True
    

    def validate_password(self, user_email: str, password: str) -> bool:
        return self.users.validate_password(user_email, password)


    def update(self, user_email: str, **fields) -> User:
        user = self.users.update(user_email, **fields)
        return user_from_record(user)

    def delete(self, user_email: str) -> User:
        user = self.users.delete(user_email)
        return user_from_record(user)

