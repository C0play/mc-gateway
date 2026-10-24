from ....utils.models import User
from ..models.user import User as UserModel


def user_from_record(record: User) -> UserModel:
    """Maps a user record to it's pydantic model."""
    return UserModel(email=str(record.email), role=str(record.role))
