from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from src.domain.entities.monthly_goal import MonthlyGoal
from src.domain.entities.spending import Spending
from src.domain.entities.spending_category import SpendingCategory

class SpendingRepository(ABC):
    # Categories
    @abstractmethod
    async def create_category(self, category: SpendingCategory) -> SpendingCategory:
        pass

    @abstractmethod
    async def delete_category(self, category_id: UUID) -> bool:
        pass

    @abstractmethod
    async def get_category_by_id(self, category_id: UUID) -> Optional[SpendingCategory]:
        pass

    @abstractmethod
    async def get_category_by_name(self, name: str) -> Optional[SpendingCategory]:
        pass

    @abstractmethod
    async def get_all_categories(self) -> list[SpendingCategory]:
        pass

    # Monthly Goals
    @abstractmethod
    async def create_monthly_goal(self, monthly_goal: MonthlyGoal) -> MonthlyGoal:
        pass

    @abstractmethod
    async def get_monthly_goal(self, client_id: UUID, category_id: UUID, year_month: date) -> Optional[MonthlyGoal]:
        pass

    @abstractmethod
    async def get_monthly_goals_by_client_and_month(self, client_id: UUID, year_month: date) -> list[MonthlyGoal]:
        pass

    @abstractmethod
    async def update_monthly_goal(self, monthly_goal: MonthlyGoal) -> MonthlyGoal:
        pass

    @abstractmethod
    async def get_monthly_goals_pending_80_alert(self, year_month: date) -> list[MonthlyGoal]:
        pass

    @abstractmethod
    async def get_monthly_goals_pending_100_alert(self, year_month: date) -> list[MonthlyGoal]:
        pass

    # Spendings
    @abstractmethod
    async def create_spending(self, spending: Spending) -> Spending:
        pass

    @abstractmethod
    async def get_spendings_by_client_and_month(self, client_id: UUID, year_month: date) -> list[Spending]:
        pass

    @abstractmethod
    async def get_spendings_by_client_category_and_month(self, client_id: UUID, category_id: UUID, year_month: date) -> list[Spending]:
        pass
