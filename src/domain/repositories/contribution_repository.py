from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.contribution import Contribution


class ContributionRepository(ABC):
    @abstractmethod
    async def create(self, contribution: Contribution) -> Contribution:
        pass

    @abstractmethod
    async def get_by_goal_id(self, goal_id: UUID) -> list[Contribution]:
        pass
