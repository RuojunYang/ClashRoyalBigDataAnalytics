from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operation: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    params: dict | None
    progress: dict | None
    result: dict | None
    error_message: str | None
