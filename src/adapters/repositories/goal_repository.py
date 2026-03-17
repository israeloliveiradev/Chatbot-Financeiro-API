from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.goal import Goal as GoalEntity
from src.domain.repositories.goal_repository import GoalRepository
from src.infra.database.models import GoalModel

class GoalRepositoryImpl(GoalRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: GoalModel) -> GoalEntity:
        return GoalEntity(
            id=model.id,
            client_id=model.client_id,
            title=model.title,
            target_amount=model.target_amount,
            current_amount=model.current_amount,
            deadline=model.deadline,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, entity: GoalEntity) -> GoalModel:
        return GoalModel(
            id=entity.id,
            client_id=entity.client_id,
            title=entity.title,
            target_amount=entity.target_amount,
            current_amount=entity.current_amount,
            deadline=entity.deadline,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )

    async def get_by_id(self, goal_id: UUID) -> Optional[GoalEntity]:
        stmt = select(GoalModel).where(GoalModel.id == goal_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_client_id(self, client_id: UUID) -> list[GoalEntity]:
        stmt = select(GoalModel).where(GoalModel.client_id == client_id).order_by(GoalModel.created_at.desc())
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def create(self, goal: GoalEntity) -> GoalEntity:
        model = self._to_model(goal)
        self.session.add(model)
        await self.session.flush()
        await self.session.commit()
        return self._to_entity(model)

    async def update(self, goal: GoalEntity) -> GoalEntity:
        model = self._to_model(goal)
        merged = await self.session.merge(model)
        await self.session.flush()
        await self.session.commit()
        return self._to_entity(merged)
