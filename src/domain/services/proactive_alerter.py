import logging
from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.repositories.spending_repository import SpendingRepository
from src.adapters.messaging.evolution_client import EvolutionClient

logger = logging.getLogger(__name__)

class ProactiveAlerter:
    def __init__(self, spending_repo: SpendingRepository, evolution_client: EvolutionClient):
        self.spending_repo = spending_repo
        self.evolution_client = evolution_client

    async def check_spending_alerts(self, client_id: UUID, phone: str, category_id: UUID) -> None:
        """
        Verifica se o gasto na categoria atingiu 80% ou 100% da meta e envia alerta se necessário.
        """
        today = date.today()
        year_month = today.replace(day=1)

        # 1. Busca meta mensal para a categoria
        goal = await self.spending_repo.get_monthly_goal(client_id, category_id, year_month)
        if not goal or goal.limit_amount <= 0:
            return

        # 2. Busca total gasto no mês para a categoria
        spendings = await self.spending_repo.get_spendings_by_client_and_month(client_id, year_month)
        total_spent = sum([s.amount for s in spendings if s.category_id == category_id], Decimal("0.00"))

        percentage = (total_spent / goal.limit_amount) * 100

        # 3. Verifica limites e envia alertas
        # Alerta 100% (Prioridade)
        if percentage >= 100 and not goal.alert_100_sent:
            msg = (
                f"🚨 *ALERTA DE LIMITE EXCEDIDO* 🚨\n\n"
                f"Atenção! Você ultrapassou 100% da sua meta de gastos em uma categoria:\n\n"
                f"• Categoria: *{await self._get_cat_name(category_id)}*\n"
                f"• Meta: *R$ {goal.limit_amount:.2f}*\n"
                f"• Gasto: *R$ {total_spent:.2f}* ({(percentage):.1f}%)\n\n"
                f"Vamos conversar sobre como ajustar o orçamento para o restante do mês? 👀"
            )
            await self.evolution_client.send_text_message(phone, msg)
            goal.alert_100_sent = True
            await self.spending_repo.update_monthly_goal(goal)
            logger.info(f"[ALERTER] Alerta 100% enviado para {phone} - Categoria {category_id}")

        # Alerta 80%
        elif percentage >= 80 and not goal.alert_80_sent:
            msg = (
                f"⚠️ *ALERTA DE LIMITE PRÓXIMO* ⚠️\n\n"
                f"Fique de olho! Você atingiu 80% da sua meta de gastos:\n\n"
                f"• Categoria: *{await self._get_cat_name(category_id)}*\n"
                f"• Meta: *R$ {goal.limit_amount:.2f}*\n"
                f"• Gasto: *R$ {total_spent:.2f}* ({(percentage):.1f}%)\n\n"
                f"Ainda restam alguns dias no mês. Tente segurar um pouco os gastos nessa categoria! 💪"
            )
            await self.evolution_client.send_text_message(phone, msg)
            goal.alert_80_sent = True
            await self.spending_repo.update_monthly_goal(goal)
            logger.info(f"[ALERTER] Alerta 80% enviado para {phone} - Categoria {category_id}")

    async def _get_cat_name(self, category_id: UUID) -> str:
        categories = await self.spending_repo.get_all_categories()
        for cat in categories:
            if cat.id == category_id:
                return cat.name
        return "Categoria"
