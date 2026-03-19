import calendar
from datetime import date, datetime, time, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.monthly_goal import MonthlyGoal as MonthlyGoalEntity
from src.domain.entities.spending import Spending as SpendingEntity
from src.domain.entities.spending_category import SpendingCategory as SpendingCategoryEntity
from src.domain.repositories.spending_repository import SpendingRepository
from src.infra.database.models import MonthlyGoalModel, SpendingModel, SpendingCategoryModel

class SpendingRepositoryImpl(SpendingRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _category_to_entity(self, model: SpendingCategoryModel) -> SpendingCategoryEntity:
        return SpendingCategoryEntity(id=model.id, name=model.name)

    def _category_to_model(self, entity: SpendingCategoryEntity) -> SpendingCategoryModel:
        return SpendingCategoryModel(id=entity.id, name=entity.name)

    def _monthly_goal_to_entity(self, model: MonthlyGoalModel) -> MonthlyGoalEntity:
        return MonthlyGoalEntity(
            id=model.id,
            client_id=model.client_id,
            category_id=model.category_id,
            year_month=model.year_month,
            limit_amount=model.limit_amount,
            alert_80_sent=model.alert_80_sent,
            alert_100_sent=model.alert_100_sent
        )

    def _monthly_goal_to_model(self, entity: MonthlyGoalEntity) -> MonthlyGoalModel:
        return MonthlyGoalModel(
            id=entity.id,
            client_id=entity.client_id,
            category_id=entity.category_id,
            year_month=entity.year_month,
            limit_amount=entity.limit_amount,
            alert_80_sent=entity.alert_80_sent,
            alert_100_sent=entity.alert_100_sent
        )

    def _spending_to_entity(self, model: SpendingModel) -> SpendingEntity:
        return SpendingEntity(
            id=model.id,
            client_id=model.client_id,
            category_id=model.category_id,
            amount=model.amount,
            description=model.description,
            spent_at=model.spent_at
        )

    def _spending_to_model(self, entity: SpendingEntity) -> SpendingModel:
        return SpendingModel(
            id=entity.id,
            client_id=entity.client_id,
            category_id=entity.category_id,
            amount=entity.amount,
            description=entity.description,
            spent_at=entity.spent_at
        )

    # ── Categories ───────────────────────────────────────────────────────────

    async def create_category(self, category: SpendingCategoryEntity) -> SpendingCategoryEntity:
        model = self._category_to_model(category)
        self.session.add(model)
        await self.session.flush()
        return self._category_to_entity(model)

    async def delete_category(self, category_id: UUID) -> bool:
        stmt = select(SpendingCategoryModel).where(SpendingCategoryModel.id == category_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.flush()
            return True
        return False

    async def get_category_by_id(self, category_id: UUID) -> Optional[SpendingCategoryEntity]:
        stmt = select(SpendingCategoryModel).where(SpendingCategoryModel.id == category_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._category_to_entity(model) if model else None

    async def get_category_by_name(self, name: str) -> Optional[SpendingCategoryEntity]:
        stmt = select(SpendingCategoryModel).where(SpendingCategoryModel.name == name)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._category_to_entity(model) if model else None

    async def get_all_categories(self) -> List[SpendingCategoryEntity]:
        stmt = select(SpendingCategoryModel).order_by(SpendingCategoryModel.name)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._category_to_entity(m) for m in models]

    # ── Monthly Goals ────────────────────────────────────────────────────────

    async def create_monthly_goal(self, monthly_goal: MonthlyGoalEntity) -> MonthlyGoalEntity:
        model = self._monthly_goal_to_model(monthly_goal)
        self.session.add(model)
        await self.session.flush()
        return self._monthly_goal_to_entity(model)

    async def get_monthly_goal(self, client_id: UUID, category_id: UUID, year_month: date) -> Optional[MonthlyGoalEntity]:
        stmt = select(MonthlyGoalModel).where(
            and_(
                MonthlyGoalModel.client_id == client_id,
                MonthlyGoalModel.category_id == category_id,
                MonthlyGoalModel.year_month == year_month
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._monthly_goal_to_entity(model) if model else None

    async def get_monthly_goals_by_client_and_month(self, client_id: UUID, year_month: date) -> List[MonthlyGoalEntity]:
        stmt = select(MonthlyGoalModel).where(
            and_(
                MonthlyGoalModel.client_id == client_id,
                MonthlyGoalModel.year_month == year_month
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._monthly_goal_to_entity(m) for m in models]

    async def update_monthly_goal(self, monthly_goal: MonthlyGoalEntity) -> MonthlyGoalEntity:
        model = self._monthly_goal_to_model(monthly_goal)
        merged = await self.session.merge(model)
        await self.session.flush()
        return self._monthly_goal_to_entity(merged)

    async def get_monthly_goals_pending_80_alert(self, year_month: date) -> List[MonthlyGoalEntity]:
        stmt = select(MonthlyGoalModel).where(
            and_(
                MonthlyGoalModel.year_month == year_month,
                MonthlyGoalModel.alert_80_sent == False,
                MonthlyGoalModel.alert_100_sent == False  # Evita alerta 80 se já atingiu 100
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._monthly_goal_to_entity(m) for m in models]

    async def get_monthly_goals_pending_100_alert(self, year_month: date) -> List[MonthlyGoalEntity]:
        stmt = select(MonthlyGoalModel).where(
            and_(
                MonthlyGoalModel.year_month == year_month,
                MonthlyGoalModel.alert_100_sent == False
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._monthly_goal_to_entity(m) for m in models]

    # ── Spendings ────────────────────────────────────────────────────────────

    async def create_spending(self, spending: SpendingEntity) -> SpendingEntity:
        model = self._spending_to_model(spending)
        self.session.add(model)
        await self.session.flush()
        return self._spending_to_entity(model)

    def _month_bounds(self, reference_date: date):
        _, last_day = calendar.monthrange(reference_date.year, reference_date.month)
        start_date = datetime.combine(reference_date.replace(day=1), time.min, tzinfo=timezone.utc)
        end_date = datetime.combine(reference_date.replace(day=last_day), time.max, tzinfo=timezone.utc)
        return start_date, end_date

    async def get_spendings_by_client_and_month(self, client_id: UUID, year_month: date) -> List[SpendingEntity]:
        start, end = self._month_bounds(year_month)
        stmt = select(SpendingModel).where(
            and_(
                SpendingModel.client_id == client_id,
                SpendingModel.spent_at >= start,
                SpendingModel.spent_at <= end
            )
        ).order_by(SpendingModel.spent_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._spending_to_entity(m) for m in models]

    async def get_spendings_by_client_category_and_month(self, client_id: UUID, category_id: UUID, year_month: date) -> List[SpendingEntity]:
        start, end = self._month_bounds(year_month)
        stmt = select(SpendingModel).where(
            and_(
                SpendingModel.client_id == client_id,
                SpendingModel.category_id == category_id,
                SpendingModel.spent_at >= start,
                SpendingModel.spent_at <= end
            )
        ).order_by(SpendingModel.spent_at.desc())
        
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._spending_to_entity(m) for m in models]
