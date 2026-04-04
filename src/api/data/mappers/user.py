from ....utils.models import User as UserRecord
from ..models.user import User



def user_from_record(record: UserRecord) -> User:
    return User(
        email=str(record.email),
        role=str(record.role)
    )