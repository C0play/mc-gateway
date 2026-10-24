from abc import ABC, abstractmethod

from peewee import DoesNotExist, IntegrityError

from ....exceptions.errors import ConflictError, NotFoundError, ServiceError
from ....security.hashing import hash_password, verify_password
from ....security.tokens import generate_token_bytes
from ....utils.models import User
from ..mappers.user import user_from_record
from ..models.user import User as UserModel


class BaseUserRepository(ABC):
    """A base class for managing whitelist parameters stored in persistent storage"""

    @abstractmethod
    def create(self, email: str, password: str, role: str) -> UserModel:
        """
        Creates a new User. (Password is salted and then hashed)

        Args:
            email: The users's email.
            password: Plain text password set by the user.
            role: Role assigned to the user.

        Returns:
            user: User model instance.

        Raises:
            ConflictError: If the user with the specified email already exists.
        """
        ...

    @abstractmethod
    def read(self, **filters) -> list[UserModel]:
        """
        Retrieves User records matching the given filters.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            list[UserModel]: Matching User model instances.
        """
        ...

    @abstractmethod
    def read_one(self, **filters) -> UserModel:
        """
        Retrieves a single User record matching the given filters.
        If multiple records match, only one is returned.

        Args:
            **filters: Field names and values to filter by.

        Returns:
            UserModel: Matching User model instance.
        """
        ...

    @abstractmethod
    def validate_password(self, email: str, password: str) -> bool:
        """
        Validates a user's password.

        Args:
            user_email: The users's email.
            password: Plain text password sent by the user.

        Returns:
            bool: True if the hashed password maches the provided one, False otherwise.
        """
        ...

    @abstractmethod
    def update(self, user_email: str, **fields) -> UserModel:
        """
        Updates arbitrary fields on a User record.

        Args:
            user_email: The user's email address.
            **fields: Field names and their new values.

        Returns:
            UserModel: The updated User instance.

        Raises:
            NotFoundError: If the user does not exist.
        """
        ...

    @abstractmethod
    def delete(
        self,
        user_email: str,
    ) -> UserModel:
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

    def create(self, email: str, password: str, role: str) -> UserModel:
        try:
            salt = generate_token_bytes(16)
            passwd_hash = hash_password(password, salt)
            record = User.create(
                email=email,
                passwd_salt=salt.hex(),
                passwd_hash=passwd_hash,
                role=role,
            )
            return user_from_record(record)
        except IntegrityError as e:
            raise ConflictError(f"failed to create User: {e}")
        except Exception as e:
            raise ServiceError(f"unexpected error while creating a new User: {e}")

    def read(self, **filters) -> list[UserModel]:
        query = User.select()
        for field, value in filters.items():
            if value is None:
                continue
            query = query.where(getattr(User, field) == value)
        return [user_from_record(r) for r in list(query)]

    def read_one(self, **filters) -> UserModel:
        try:
            return self.read(**filters)[0]
        except IndexError:
            raise NotFoundError("no matching records found")

    def validate_password(self, email: str, password: str) -> bool:
        try:
            record: User = User.get_by_id(email)
        except DoesNotExist:
            return False

        return verify_password(
            password,
            str(record.passwd_salt),
            str(record.passwd_hash),
        )

    def update(self, user_email: str, **fields) -> UserModel:
        rows = User.update(**fields).where(User.email == user_email).execute()
        if rows == 0:
            raise NotFoundError(f"User {user_email} does not exist")
        record = User.get_by_id(user_email)
        return user_from_record(record)

    def delete(
        self,
        user_email: str,
    ) -> UserModel:
        record = User.get_or_none(User.email == user_email)
        if record is None:
            raise NotFoundError(f"User {user_email} does not exist")

        rows_deleted = User.delete().where(User.email == user_email).execute()
        if rows_deleted == 0:
            raise NotFoundError(f"User {user_email} does not exist")
        return user_from_record(record)
