from ..data.mappers.api_key import apikey_from_record
from ..data.models.response import ListResponse, MessageResponse


class ApiKeyService:

    def __init__(self, *, keys) -> None:
        self.keys = keys

    
    def api_key_list_own(self, email: str, name: str | None = None) -> ListResponse:
        query = self.keys.read(user=email, name=name)
        lst = [apikey_from_record(row) for row in query]
        return ListResponse(root=lst)

    
    def api_key_create_own(self, email: str) -> MessageResponse:
        key = self.keys.create(email)
        return MessageResponse(message=key)

    
    def api_key_revoke_own(self, email: str, name: str) -> MessageResponse:
        self.keys.deactivate(email, name)
        return MessageResponse(message=f"Key {name} revoked.")