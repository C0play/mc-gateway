from pydantic import BaseModel, Field, RootModel

from .host import FullHost
from .container import FullContainer
from .player import FullPlayer
from .api_key import ApiKey


class ListResponse(RootModel):
    root: list[FullPlayer] | list[FullContainer] | list[FullHost] | list[ApiKey] = Field(
        ...,
        description="List of requested resources"
    )


class StatusResponse(BaseModel):
    clients: int
    sessions: int
    containers: int
    hosts: int


class MessageResponse(BaseModel):
    message: str