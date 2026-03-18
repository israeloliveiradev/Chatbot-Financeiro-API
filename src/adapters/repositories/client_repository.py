from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.client import Client as ClientEntity
from src.domain.repositories.client_repository import ClientRepository
from src.infra.database.models import ClientModel

class ClientRepositoryImpl(ClientRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: ClientModel) -> ClientEntity:
        return ClientEntity(
            id=model.id,
            phone=model.phone,
            name=model.name,
            monthly_income=model.monthly_income,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_model(self, entity: ClientEntity) -> ClientModel:
        return ClientModel(
            id=entity.id,
            phone=entity.phone,
            name=entity.name,
            monthly_income=entity.monthly_income,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )

    async def get_by_id(self, client_id: UUID) -> Optional[ClientEntity]:
        stmt = select(ClientModel).where(ClientModel.id == client_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_phone(self, phone: str) -> Optional[ClientEntity]:
        stmt = select(ClientModel).where(ClientModel.phone == phone)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, client: ClientEntity) -> ClientEntity:
        model = self._to_model(client)
        self.session.add(model)
        await self.session.flush()
        return self._to_entity(model)

    async def update(self, client: ClientEntity) -> ClientEntity:
        model = self._to_model(client)
        merged = await self.session.merge(model)
        await self.session.flush()
        return self._to_entity(merged)
