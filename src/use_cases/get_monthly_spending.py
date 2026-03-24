import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List
from uuid import UUID

from src.domain.repositories.spending_repository import SpendingRepository
from src.use_cases.base import BaseUseCase

logger = logging.getLogger(__name__)

class GetMonthlySpending(BaseUseCase):
    def __init__(self, spending_repo: SpendingRepository):
        self.spending_repo = spending_repo

    async def execute(self, client_id: UUID, year_month: date) -> List[Dict[str, Any]]:
        """
        Retorna o resumo de gastos e metas do mês para TODAS as categorias disponíveis.
        """
        normalized_month = year_month.replace(day=1)
        
        try:
            # 1. Busca metas, gastos e todas as categorias
            monthly_goals = await self.spending_repo.get_monthly_goals_by_client_and_month(client_id, normalized_month)
            spendings = await self.spending_repo.get_spendings_by_client_and_month(client_id, normalized_month)
            categories = await self.spending_repo.get_all_categories()
        except Exception as e:
            logger.error(f"[ERROR-SPENDING] Failed to fetch data: {str(e)}")
            raise e
        
        # 2. Mapeamentos para facilitar o resumo
        # Meta por Categoria ID
        goals_map = {goal.category_id: goal for goal in monthly_goals}
        
        # Gasto Total por Categoria ID
        spending_totals = {}
        for sp in spendings:
            spending_totals[sp.category_id] = spending_totals.get(sp.category_id, Decimal("0.00")) + sp.amount
            
        summary = []
        
        # 3. Iteramos sobre TODAS as categorias para dar o contexto completo ao LLM
        for cat in categories:
            goal = goals_map.get(cat.id)
            total_spent = spending_totals.get(cat.id, Decimal("0.00"))
            
            limit_amount = goal.limit_amount if goal else Decimal("0.00")
            available = limit_amount - total_spent
            
            # Só incluímos no resumo se houver meta OU gasto (para não poluir demais)
            # Ou incluímos tudo se quisermos que o LLM conheça as opções (melhor incluir tudo se for lista curta)
            if limit_amount > 0 or total_spent > 0:
                summary.append({
                    "category": cat.name,
                    "limit_amount": float(limit_amount),
                    "total_spent": float(total_spent),
                    "available": float(available),
                    "percentage_used": round(float(total_spent / limit_amount * 100), 2) if limit_amount > 0 else 0
                })
            
        return summary
