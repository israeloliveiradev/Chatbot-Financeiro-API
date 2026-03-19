from datetime import datetime
from pydantic import BaseModel, Field
from typing import List

class ClientResponse(BaseModel):
    id: str
    phone: str
    name: str | None
    monthly_income: float
    
class ClientCreateRequest(BaseModel):
    phone: str
    name: str | None = None
    monthly_income: float = Field(default=0.0)


class GoalResponse(BaseModel):
    id: str
    title: str
    target_amount: float
    current_amount: float
    status: str
    deadline: str | None


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    target_amount: float | None = Field(default=None, gt=0)
    deadline: str | None = None
    status: str | None = None


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class CategoryResponse(BaseModel):
    id: str
    name: str


class SpendingSummaryResponse(BaseModel):
    category: str
    limit_amount: float
    total_spent: float
    available: float
    percentage_used: float


class TransactionCreateRequest(BaseModel):
    category_name: str
    amount: float = Field(..., gt=0)
    description: str | None = None
    spent_at: datetime | None = None


class TransactionResponse(BaseModel):
    id: str
    category_id: str
    category_name: str
    amount: float
    description: str | None
    spent_at: str


class MonthlyGoalCreateRequest(BaseModel):
    category_name: str
    limit_amount: float = Field(..., gt=0)
    year_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class MonthlyGoalResponse(BaseModel):
    id: str
    category_name: str
    limit_amount: float
    year_month: str
    alert_80_sent: bool
    alert_100_sent: bool


class StandardResponse(BaseModel):
    data: dict | list | None = None
    message: str = "Operação realizada com sucesso"
