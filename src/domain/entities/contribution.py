from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Contribution(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    goal_id: UUID
    amount: Decimal = Field(decimal_places=2)
    note: str | None = None
    contributed_at: datetime = Field(default_factory=datetime.utcnow)
