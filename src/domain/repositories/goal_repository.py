from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.goal import Goal


class GoalRepository(ABC):
    @abstractmethod
    async def get_by_id(self, goal_id: UUID) -> Optional[Goal]:
        pass

    @abstractmethod
    async def get_by_client_id(self, client_id: UUID) -> list[Goal]:
        pass

    @abstractmethod
    async def create(self, goal: Goal) -> Goal:
        pass

    @abstractmethod
    async def update(self, goal: Goal) -> Goal:
        pass
