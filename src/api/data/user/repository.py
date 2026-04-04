from abc import ABC, abstractmethod

from peewee import IntegrityError, DoesNotExist

from ....utils.models import User
from ....exceptions.errors import NotFoundError, ConflictError, ServiceError
from ....security.hashing import hash_password, verify_password
from ....security.tokens import generate_token_bytes



class BaseUserRepository(ABC):
    """A base class for managing whitelist parameters stored in persistent storage"""
    
    @abstractmethod
    def create(self, user_email: str, password: str, role: str) -> User:
        """
        Creates a new User. (Password is salted and then hashed)

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
    def validate_password(self, email: str, password: str) -> bool:
        """
        Validates user password.

        Args:
            user_email: The users's email.
            password: Plain text password sent by the user.

        Returns:
            bool: True if the hashed password maches the provided one, False otherwise.
        """
        ...
    
    @abstractmethod
    def update(self, user_email: str, **fields) -> User:
        """
        Updates arbitrary fields on a User record.

        Args:
            user_email: The user's email address.
            **fields: Field names and their new values.

        Returns:
            User: The updated User instance.

        Raises:
            NotFoundError: If the user does not exist.
        """
        ...

    @abstractmethod
    def delete(self, user_email: str,) -> User:
        """
        Removes a User record by user_email.

        Args:
            user_email: The email of the User to remove.

        Raises:
            NotFoundError: If the User does not exist.
        """
        ...



class SQLUserRepository(BaseUserRepository):
    """
    Implementation of host storage using Peewee ORM.
    """
    
    def create(self, user_email: str, password: str, role: str) -> User:
        try:
            salt = generate_token_bytes(16)
            passwd_hash = hash_password(password, salt)
            user = User.create(
                email=user_email,
                passwd_salt=salt.hex(),
                passwd_hash=passwd_hash,
                role=role,
            )
            return user
        except IntegrityError as e:
            raise ConflictError(f"failed to create User: {e}")
        except Exception as e:
            raise ServiceError(f"unexpected error while creating a new User: {e}")


    def read(self, **filters) -> list[User]:
        query = User.select()
        for field, value in filters.items():
            if value is None:
                continue
            query = query.where(getattr(User, field) == value)
        return list(query)


    def validate_password(self, email: str, password: str) -> bool:
        try:
            user: User = User.get_by_id(email)
        except DoesNotExist:
            return False

        return verify_password(
            password,
            str(user.passwd_salt),
            str(user.passwd_hash),
        )


    def update(self, user_email: str, **fields) -> User:
        rows = (User
                    .update(**fields)
                    .where(User.email == user_email)
                    .execute())
        if rows == 0:
            raise NotFoundError(f"User {user_email} does not exist")
        return User.get_by_id(user_email)


    def delete(self, user_email: str,) -> User:
        record = User.get_or_none(User.email == user_email)
        if record is None:
            raise NotFoundError(f"User {user_email} does not exist")

        rows_deleted = (User
                        .delete()
                        .where(User.email == user_email)
                        .execute())
        if rows_deleted == 0:
            raise NotFoundError(f"User {user_email} does not exist")
        return record