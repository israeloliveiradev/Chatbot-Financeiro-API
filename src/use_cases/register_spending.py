from typing import Optional
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime

from src.domain.entities.spending import Spending
from src.domain.repositories.spending_repository import SpendingRepository
from src.use_cases.base import BaseUseCase

class RegisterSpending(BaseUseCase):
    def __init__(self, spending_repo: SpendingRepository):
        self.spending_repo = spending_repo

    async def execute(
        self,
        client_id: UUID,
        category_name: str,
        amount: Decimal,
        description: Optional[str] = None,
        spent_at: Optional[datetime] = None
    ) -> Spending:
        """
        Registra um novo gasto para o cliente.
        """
        # 1. Buscar ou criar categoria
        category = await self.spending_repo.get_category_by_name(category_name)
        if not category:
            # Fallback para 'Outros' se existir, ou a primeira categoria disponível
            category = await self.spending_repo.get_category_by_name("Outros")
            if not category:
                categories = await self.spending_repo.get_all_categories()
                if not categories:
                    raise ValueError(f"Nenhuma categoria encontrada no sistema.")
                category = categories[0]

        spending = Spending(
            id=uuid4(),
            client_id=client_id,
            category_id=category.id,
            amount=amount,
            description=description,
            spent_at=spent_at or datetime.now()
        )
        
        await self.spending_repo.create_spending(spending)
        return spending
