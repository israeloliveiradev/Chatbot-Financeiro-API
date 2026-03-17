from uuid import UUID

from src.domain.entities.goal import Goal
from src.domain.repositories.goal_repository import GoalRepository

class GetGoals:
    def __init__(self, goal_repo: GoalRepository):
        self.goal_repo = goal_repo

    async def execute(self, client_id: UUID, only_active: bool = True) -> list[Goal]:
        """
        Busca os objetivos financeiros de um cliente.
        """
        goals = await self.goal_repo.get_by_client_id(client_id)
        if only_active:
            goals = [g for g in goals if g.status == "active"]
        return goals
