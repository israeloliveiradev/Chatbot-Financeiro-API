from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import date

from src.domain.entities.spending import Spending
from src.domain.repositories.spending_repository import SpendingRepository

class RegisterSpending:
    def __init__(self, spending_repo: SpendingRepository):
        self.spending_repo = spending_repo

    async def execute(self, client_id: UUID, category_name: str, amount: Decimal, description: Optional[str] = None) -> Spending:
        # Busca a categoria pelo nome ou cria uma genérica? 
        # Por simplicidade senior, vamos buscar. Se não existir, erro.
        category = await self.spending_repo.get_category_by_name(category_name)
        if not category:
            # Fallback para 'Outros' se existir, ou erro
            category = await self.spending_repo.get_category_by_name("Outros")
            if not category:
                raise ValueError(f"Categoria '{category_name}' não encontrada no sistema.")

        spending = Spending(
            client_id=client_id,
            category_id=category.id,
            amount=amount,
            description=description,
            date=date.today()
        )
        
        # O commit será via UOW no Use Case orquestrador (ProcessMessage)
        return await self.spending_repo.create(spending)
