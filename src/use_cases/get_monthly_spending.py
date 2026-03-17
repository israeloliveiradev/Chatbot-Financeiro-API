from datetime import date
from decimal import Decimal
from typing import Dict, Any
from uuid import UUID

from src.domain.repositories.spending_repository import SpendingRepository

class GetMonthlySpending:
    def __init__(self, spending_repo: SpendingRepository):
        self.spending_repo = spending_repo

    async def execute(self, client_id: UUID, year_month: date) -> list[Dict[str, Any]]:
        """
        Retorna o resumo de gastos e metas do mês para cada categoria do cliente.
        Isso ajuda o LLM a ter o contexto completo do mês.
        """
        # Sempre garantindo que seja o dia 1 do mês para busca correta nas metas
        normalized_month = year_month.replace(day=1)
        
        monthly_goals = await self.spending_repo.get_monthly_goals_by_client_and_month(client_id, normalized_month)
        spendings = await self.spending_repo.get_spendings_by_client_and_month(client_id, normalized_month)
        categories = await self.spending_repo.get_all_categories()
        
        category_map = {cat.id: cat.name for cat in categories}
        
        # Agrupar os gastos por categoria
        spending_totals = {}
        for sp in spendings:
            spending_totals[sp.category_id] = spending_totals.get(sp.category_id, Decimal("0.00")) + sp.amount
            
        summary = []
        for goal in monthly_goals:
            cat_name = category_map.get(goal.category_id, "Desconhecida")
            total_spent = spending_totals.get(goal.category_id, Decimal("0.00"))
            available = goal.limit_amount - total_spent
            
            summary.append({
                "category": cat_name,
                "limit_amount": float(goal.limit_amount),
                "total_spent": float(total_spent),
                "available": float(available),
                "percentage_used": round(float(total_spent / goal.limit_amount * 100), 2) if goal.limit_amount > 0 else 0
            })
            
        return summary
