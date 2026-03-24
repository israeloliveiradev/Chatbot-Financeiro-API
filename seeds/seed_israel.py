import asyncio
import logging
from datetime import date, timedelta, datetime
from decimal import Decimal
from uuid import uuid4

from src.infra.database.session import AsyncSessionLocal
from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.contribution_repository import ContributionRepositoryImpl
from src.domain.entities.client import Client
from src.domain.entities.goal import Goal
from src.domain.entities.monthly_goal import MonthlyGoal
from src.domain.entities.spending import Spending
from src.domain.entities.spending_category import SpendingCategory
from src.domain.entities.contribution import Contribution

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_israel():
    phone = "5511961605602"
    async with AsyncSessionLocal() as session:
        client_repo = ClientRepositoryImpl(session)
        goal_repo = GoalRepositoryImpl(session)
        spending_repo = SpendingRepositoryImpl(session)
        contribution_repo = ContributionRepositoryImpl(session)

        # 1. Garantir Cliente
        client = await client_repo.get_by_phone(phone)
        if not client:
            logger.info(f"Criando cliente {phone}")
            client = Client(
                id=uuid4(),
                phone=phone,
                name="Israel Oliveira",
                monthly_income=Decimal("15000.00")
            )
            await client_repo.create(client)
        else:
            logger.info(f"Cliente {phone} já existe")

        # 2. Garantir Categorias Base
        categories_names = ["Alimentação", "Transporte", "Lazer", "Contas Fixas", "Saúde", "Educação", "Outros"]
        category_objs = {}
        for name in categories_names:
            cat = await spending_repo.get_category_by_name(name)
            if not cat:
                cat = SpendingCategory(id=uuid4(), name=name)
                await spending_repo.create_category(cat)
            category_objs[name] = cat

        # 3. Metas Mensais (Budgets) para Março 2026
        current_month = date.today().replace(day=1)
        budgets = {
            "Alimentação": Decimal("2500.00"),
            "Transporte": Decimal("800.00"),
            "Lazer": Decimal("1500.00"),
            "Contas Fixas": Decimal("5000.00"),
            "Saúde": Decimal("500.00")
        }
        
        for cat_name, limit in budgets.items():
            cat = category_objs[cat_name]
            existing_goal = await spending_repo.get_monthly_goal(client.id, cat.id, current_month)
            if not existing_goal:
                logger.info(f"Criando meta de {limit} para {cat_name}")
                m_goal = MonthlyGoal(
                    id=uuid4(),
                    client_id=client.id,
                    category_id=cat.id,
                    year_month=current_month,
                    limit_amount=limit
                )
                await spending_repo.create_monthly_goal(m_goal)

        # 4. Objetivos (Goals)
        goals_data = [
            {"title": "Viagem para Europa", "target": Decimal("30000.00"), "current": Decimal("5000.00"), "deadline": date(2027, 12, 31)},
            {"title": "Reserva de Emergência", "target": Decimal("90000.00"), "current": Decimal("12000.00"), "deadline": date(2026, 6, 30)},
            {"title": "Novo Macbook Pro", "target": Decimal("25000.00"), "current": Decimal("2000.00"), "deadline": date(2026, 12, 20)}
        ]
        
        active_goals = await goal_repo.get_by_client_id(client.id)
        existing_titles = [g.title for g in active_goals]
        
        for g_data in goals_data:
            if g_data["title"] not in existing_titles:
                logger.info(f"Criando objetivo: {g_data['title']}")
                goal = Goal(
                    id=uuid4(),
                    client_id=client.id,
                    title=g_data["title"],
                    target_amount=g_data["target"],
                    current_amount=g_data["current"],
                    deadline=g_data["deadline"],
                    status="active"
                )
                await goal_repo.create(goal)

        # 5. Gastos Fictícios (Últimos 15 dias)
        logger.info("Gerando histórico de gastos...")
        descriptions = {
            "Alimentação": ["iFood", "Supermercado Pão de Açúcar", "Restaurante japonês", "Cafeteria Starbucks"],
            "Transporte": ["Uber para o trabalho", "Abastecimento Posto BR", "Recarga Bilhete Único"],
            "Lazer": ["Cinema", "Show Coldplay", "Barzinho com amigos", "Steam Game"],
            "Contas Fixas": ["Aluguel", "Energia Enel", "Internet Vivo Fiber", "Condomínio"]
        }
        
        for i in range(15):
            ref_date = datetime.now() - timedelta(days=i)
            # 1 a 3 gastos por dia
            import random
            for _ in range(random.randint(1, 3)):
                cat_name = random.choice(list(descriptions.keys()))
                cat = category_objs[cat_name]
                amount = Decimal(str(random.uniform(20.0, 300.0))).quantize(Decimal("0.00"))
                if cat_name == "Contas Fixas" and i > 10: continue # Evitar duplicar aluguel todo dia
                
                sp = Spending(
                    id=uuid4(),
                    client_id=client.id,
                    category_id=cat.id,
                    amount=amount,
                    description=random.choice(descriptions[cat_name]),
                    spent_at=ref_date
                )
                await spending_repo.create_spending(sp)

        await session.commit()
        logger.info("Seed concluído com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed_israel())
