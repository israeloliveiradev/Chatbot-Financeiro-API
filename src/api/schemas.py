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

class SpendingSummaryResponse(BaseModel):
    category: str
    limit_amount: float
    total_spent: float
    available: float
    percentage_used: float

class StandardResponse(BaseModel):
    data: dict | list | None = None
    message: str = "Operação realizada com sucesso"
