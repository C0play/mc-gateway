from ..data.mappers.api_key import apikey_from_record
from ..data.models.response import ListResponse, MessageResponse
from ..data.api_key.manager import BaseKeyManager


class ApiKeyService:

    def __init__(self, *, keys: BaseKeyManager) -> None:
        self.keys = keys

    
    def read(self, email: str | None = None, name: str | None = None) -> ListResponse:
        query = self.keys.read(user=email, name=name)
        lst = [apikey_from_record(row) for row in query]
        return ListResponse(root=lst)

    
    def create(self, email: str, name: str) -> MessageResponse:
        key = self.keys.create(email, name)
        return MessageResponse(message=key)

    
    def revoke(self, email: str, name: str) -> MessageResponse:
        self.keys.deactivate(email, name)
        return MessageResponse(message=f"Key {name} revoked.")