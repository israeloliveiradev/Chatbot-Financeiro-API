from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class MonthlyGoal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID
    category_id: UUID
    year_month: date
    limit_amount: Decimal = Field(decimal_places=2)
    alert_80_sent: bool = False
    alert_100_sent: bool = False
