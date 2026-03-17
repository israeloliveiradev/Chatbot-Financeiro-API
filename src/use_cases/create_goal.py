from datetime import date
from decimal import Decimal
from uuid import UUID

from src.domain.entities.goal import Goal
from src.domain.repositories.goal_repository import GoalRepository

class CreateGoal:
    def __init__(self, goal_repo: GoalRepository):
        self.goal_repo = goal_repo

    async def execute(
        self, 
        client_id: UUID, 
        title: str, 
        target_amount: Decimal, 
        deadline: date | None = None
    ) -> Goal:
        """
        Cria um novo objetivo financeiro para o cliente, já assumindo o saldo inicial como 0.
        """
        new_goal = Goal(
            client_id=client_id,
            title=title,
            target_amount=target_amount,
            deadline=deadline
        )
        return await self.goal_repo.create(new_goal)
