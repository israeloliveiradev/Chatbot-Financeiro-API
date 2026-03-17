from datetime import date
from decimal import Decimal
from typing import Dict, Any
from uuid import UUID

from src.domain.repositories.spending_repository import SpendingRepository

class SimulatePurchase:
    def __init__(self, spending_repo: SpendingRepository):
        self.spending_repo = spending_repo

    async def execute(self, client_id: UUID, category_name: str, purchase_amount: Decimal, current_date: date) -> Dict[str, Any]:
        """
        Simula uma compra validando contra o limite da categoria.
        Retorna se é possível comprar e detalhes do orçamento.
        """
        category = await self.spending_repo.get_category_by_name(category_name)
        if not category:
            return {"can_buy": False, "reason": "Categoria não encontrada ou não informada."}

        normalized_month = current_date.replace(day=1)
        
        goal = await self.spending_repo.get_monthly_goal(client_id, category.id, normalized_month)
        if not goal:
            return {"can_buy": False, "reason": "Sem meta definida para essa categoria."}

        spendings = await self.spending_repo.get_spendings_by_client_category_and_month(client_id, category.id, normalized_month)
        total_spent = sum(sp.amount for sp in spendings)
        
        available = goal.limit_amount - total_spent
        can_buy = available >= purchase_amount
        
        return {
            "can_buy": can_buy,
            "category": category.name,
            "limit": float(goal.limit_amount),
            "current_spent": float(total_spent),
            "available_before": float(available),
            "available_after": float(available - purchase_amount) if can_buy else float(available),
            "purchase_amount": float(purchase_amount)
        }
