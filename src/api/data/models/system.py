from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    clients: int
    sessions: int
    containers: int
    hosts: int


TaskStatus = Literal["rejected", "processing", "completed", "failed"]


class TaskInfo(BaseModel):
    status: TaskStatus = Field(description="Task status.")
    id: str = Field(description="Task identifier.")
    container_name: str = Field(description="Container name.")
    job: str = Field(description="Job name.")
    created_time: datetime = Field(description="Time when the task was submitted")
    completed_time: datetime | None = Field(
        None, description="Time when the task was completed"
    )
