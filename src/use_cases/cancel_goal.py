from uuid import UUID

from src.domain.entities.goal import Goal
from src.domain.repositories.goal_repository import GoalRepository

class CancelGoal:
    def __init__(self, goal_repo: GoalRepository):
        self.goal_repo = goal_repo

    async def execute(self, goal_id: UUID) -> Goal:
        """
        Cancela um objetivo financeiro.
        """
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        goal.status = "cancelled"
        return await self.goal_repo.update(goal)
