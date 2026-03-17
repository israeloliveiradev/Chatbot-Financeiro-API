from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.contribution import Contribution as ContributionEntity
from src.domain.repositories.contribution_repository import ContributionRepository
from src.infra.database.models import ContributionModel

class ContributionRepositoryImpl(ContributionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: ContributionModel) -> ContributionEntity:
        return ContributionEntity(
            id=model.id,
            goal_id=model.goal_id,
            amount=model.amount,
            note=model.note,
            contributed_at=model.contributed_at
        )

    def _to_model(self, entity: ContributionEntity) -> ContributionModel:
        return ContributionModel(
            id=entity.id,
            goal_id=entity.goal_id,
            amount=entity.amount,
            note=entity.note,
            contributed_at=entity.contributed_at
        )

    async def create(self, contribution: ContributionEntity) -> ContributionEntity:
        model = self._to_model(contribution)
        self.session.add(model)
        await self.session.flush()
        return self._to_entity(model)

    async def get_by_goal_id(self, goal_id: UUID) -> list[ContributionEntity]:
        stmt = select(ContributionModel).where(ContributionModel.goal_id == goal_id).order_by(ContributionModel.contributed_at.desc())
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]
