from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Spending(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID
    category_id: UUID
    amount: Decimal = Field(decimal_places=2)
    description: str | None = None
    spent_at: datetime = Field(default_factory=datetime.utcnow)
