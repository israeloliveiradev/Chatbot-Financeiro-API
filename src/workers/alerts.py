import asyncio
from datetime import date
from decimal import Decimal
import logging
from celery import shared_task

from src.infra.database.session import AsyncSessionLocal
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.unit_of_work import SqlAlchemyUnitOfWork
from src.adapters.messaging.evolution_client import EvolutionClient

logger = logging.getLogger(__name__)

async def process_alerts():
    async with AsyncSessionLocal() as session:
        uow = SqlAlchemyUnitOfWork(session)
        spending_repo: SpendingRepository = SpendingRepositoryImpl(session)
        client_repo: ClientRepository = ClientRepositoryImpl(session)
        evolution_client = EvolutionClient()
        
        current_date = date.today()
        normalized_month = current_date.replace(day=1)
        
        async with uow:
            # Alertas de 80% (Para quem ainda não recebeu)
            goals_80 = await spending_repo.get_monthly_goals_pending_80_alert(normalized_month)
            for goal in goals_80:
                client = await client_repo.get_by_id(goal.client_id)
                if not client:
                    continue
                    
                spendings = await spending_repo.get_spendings_by_client_category_and_month(client.id, goal.category_id, normalized_month)
                total_spent = sum(sp.amount for sp in spendings)
                
                if goal.limit_amount > 0 and (total_spent / goal.limit_amount) >= Decimal("0.8"):
                    category = await spending_repo.get_category_by_id(goal.category_id)
                    cat_name = category.name if category else "Desconhecida"
                    
                    msg = f"⚠️ *Alerta de Gastos!*\nVocê já atingiu 80% do seu limite mensal para a categoria *{cat_name}*.\nLimite: R$ {goal.limit_amount}\nGasto: R$ {total_spent}"
                    try:
                        await evolution_client.send_text_message(client.phone, msg)
                        goal.alert_80_sent = True
                        await spending_repo.update_monthly_goal(goal)
                    except Exception as e:
                        logger.error(f"Erro ao enviar alerta 80% para {client.phone}: {e}")
                    
            # Alertas de 100% (Para quem já bateu a meta inteira)
            goals_100 = await spending_repo.get_monthly_goals_pending_100_alert(normalized_month)
            for goal in goals_100:
                client = await client_repo.get_by_id(goal.client_id)
                if not client:
                    continue
                    
                spendings = await spending_repo.get_spendings_by_client_category_and_month(client.id, goal.category_id, normalized_month)
                total_spent = sum(sp.amount for sp in spendings)
                
                if goal.limit_amount > 0 and (total_spent / goal.limit_amount) >= Decimal("1.0"):
                    category = await spending_repo.get_category_by_id(goal.category_id)
                    cat_name = category.name if category else "Desconhecida"
                    
                    msg = f"🚨 *Atenção!*\nVocê atingiu 100% do seu limite mensal para a categoria *{cat_name}*.\nLimite: R$ {goal.limit_amount}\nGasto: R$ {total_spent}"
                    try:
                        await evolution_client.send_text_message(client.phone, msg)
                        # Marcar o de 80 também para não mandar atrasado se o cara gastou tudo numa lapada só
                        goal.alert_80_sent = True 
                        goal.alert_100_sent = True
                        await spending_repo.update_monthly_goal(goal)
                    except Exception as e:
                        logger.error(f"Erro ao enviar alerta 100% para {client.phone}: {e}")


@shared_task(name="src.workers.alerts.check_spending_alerts")
def check_spending_alerts():
    """
    Task Celery schedulada para rodar periodicamente (ex: de hora em hora).
    """
    logger.info("Iniciando verificação de alertas de gastos...")
    asyncio.run(process_alerts())
    logger.info("Verificação de alertas finalizada.")
