from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.domain.entities.contribution import Contribution
from src.domain.repositories.contribution_repository import ContributionRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.use_cases.base import BaseUseCase

class RegisterContribution(BaseUseCase):
    def __init__(self, contribution_repo: ContributionRepository, goal_repo: GoalRepository):
        self.contribution_repo = contribution_repo
        self.goal_repo = goal_repo

    async def execute(self, goal_id: UUID, amount: Decimal, note: Optional[str] = None) -> Contribution:
        """
        Registra um aporte a um objetivo existente.
        Atualiza o current_amount do objetivo e, se bater a meta, muda o status para completado.
        """
        goal = await self.goal_repo.get_by_id(goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        # Create contribution
        contribution = Contribution(
            goal_id=goal_id,
            amount=amount,
            note=note
        )
        saved_contribution = await self.contribution_repo.create(contribution)

        # Update goal
        goal.current_amount += amount
        if goal.current_amount >= goal.target_amount:
            goal.status = "completed"
            
        await self.goal_repo.update(goal)
        
        return saved_contribution
