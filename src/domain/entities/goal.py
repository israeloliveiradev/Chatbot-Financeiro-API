from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

GoalStatus = Literal["active", "completed", "cancelled"]

class Goal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID
    title: str
    target_amount: Decimal = Field(decimal_places=2)
    current_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    deadline: date | None = None
    status: GoalStatus = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
