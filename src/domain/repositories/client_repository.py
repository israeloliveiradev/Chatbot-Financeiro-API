from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.client import Client


class ClientRepository(ABC):
    @abstractmethod
    async def get_by_id(self, client_id: UUID) -> Optional[Client]:
        pass

    @abstractmethod
    async def get_by_phone(self, phone: str) -> Optional[Client]:
        pass

    @abstractmethod
    async def create(self, client: Client) -> Client:
        pass

    @abstractmethod
    async def update(self, client: Client) -> Client:
        pass
