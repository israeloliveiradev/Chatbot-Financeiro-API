from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Client(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    phone: str
    name: str | None = None
    monthly_income: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
