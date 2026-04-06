from pydantic import BaseModel


class StatusResponse(BaseModel):
    clients: int
    sessions: int
    containers: int
    hosts: int
