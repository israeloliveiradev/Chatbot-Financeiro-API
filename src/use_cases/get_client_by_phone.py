from typing import Optional

from src.domain.entities.client import Client
from src.domain.repositories.client_repository import ClientRepository

class GetClientByPhone:
    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    async def execute(self, phone: str) -> Optional[Client]:
        """
        Busca um cliente pelo seu número de telefone (ex: 5511999999999).
        Se não existir, retorna None.
        """
        return await self.client_repo.get_by_phone(phone)
