"""
Seed de dados para o Chatbot Financeiro.

Uso:
    python seed.py

Cria:
- 1 cliente de teste
- Categorias padrão (se não existirem)
- Metas mensais para o mês atual
- Transações de exemplo para o mês atual

O script tenta conectar no host 'db' (docker) e faz fallback para 'localhost' 
se houver erro de resolução de nome.
"""

import asyncio
import sys
from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import OperationalError

# Lê o DATABASE_URL do .env
from dotenv import load_dotenv
import os

load_dotenv()

ORIGINAL_DATABASE_URL = os.getenv("DATABASE_URL")
if not ORIGINAL_DATABASE_URL:
    print("❌ DATABASE_URL não encontrada no .env")
    sys.exit(1)

from src.infra.database.models import (
    ClientModel,
    SpendingCategoryModel,
    MonthlyGoalModel,
    SpendingModel,
)

# ── Dados do seed ─────────────────────────────────────────────────────────────

PHONE = "5511999990001"

CATEGORIES = [
    "Alimentação",
    "Transporte",
    "Moradia",
    "Saúde",
    "Educação",
    "Lazer",
    "Vestuário",
    "Assinaturas",
    "Outros",
]

MONTHLY_LIMITS = {
    "Alimentação": Decimal("1200.00"),
    "Transporte": Decimal("400.00"),
    "Moradia": Decimal("2000.00"),
    "Saúde": Decimal("300.00"),
    "Educação": Decimal("500.00"),
    "Lazer": Decimal("600.00"),
    "Vestuário": Decimal("300.00"),
    "Assinaturas": Decimal("200.00"),
    "Outros": Decimal("300.00"),
}

TRANSACTIONS = [
    ("Alimentação", "Supermercado Extra", Decimal("350.00"), -2),
    ("Alimentação", "iFood - Pizza", Decimal("85.90"), -5),
    ("Alimentação", "Padaria Central", Decimal("32.50"), -1),
    ("Alimentação", "Restaurante Almoço", Decimal("47.00"), -3),
    ("Transporte", "Uber", Decimal("28.50"), -1),
    ("Transporte", "Posto de Gasolina Shell", Decimal("180.00"), -4),
    ("Transporte", "99 Taxi", Decimal("22.00"), -2),
    ("Moradia", "Aluguel Mês", Decimal("1500.00"), -10),
    ("Moradia", "Conta de Luz", Decimal("145.00"), -8),
    ("Moradia", "Internet Vivo Fibra", Decimal("109.90"), -8),
    ("Saúde", "Farmácia Drogasil", Decimal("67.30"), -3),
    ("Saúde", "Consulta Médica", Decimal("150.00"), -12),
    ("Lazer", "Cinema Cinemark", Decimal("64.00"), -6),
    ("Lazer", "Netflix", Decimal("39.90"), -7),
    ("Vestuário", "Renner — Camiseta", Decimal("89.99"), -9),
    ("Assinaturas", "Spotify Premium", Decimal("21.90"), -1),
    ("Assinaturas", "Amazon Prime", Decimal("19.90"), -1),
    ("Educação", "Udemy — Curso Python", Decimal("49.90"), -14),
]


# ── Funções de seed ───────────────────────────────────────────────────────────

async def get_or_create_client(session: AsyncSession) -> ClientModel:
    result = await session.execute(
        select(ClientModel).where(ClientModel.phone == PHONE)
    )
    existing = result.scalar_one_or_none()
    if existing:
        print(f"  ✔ Cliente já existe: {existing.name} ({existing.phone})")
        return existing

    client = ClientModel(
        id=uuid4(),
        phone=PHONE,
        name="João Silva (Teste)",
        monthly_income=Decimal("5000.00"),
    )
    session.add(client)
    await session.flush()
    print(f"  ✔ Cliente criado: {client.name} ({client.phone})")
    return client


async def get_or_create_categories(session: AsyncSession) -> dict[str, SpendingCategoryModel]:
    result = await session.execute(select(SpendingCategoryModel))
    existing = {c.name: c for c in result.scalars().all()}

    for cat_name in CATEGORIES:
        if cat_name not in existing:
            cat = SpendingCategoryModel(id=uuid4(), name=cat_name)
            session.add(cat)
            await session.flush()
            existing[cat_name] = cat
            print(f"  ✔ Categoria criada: {cat_name}")
        else:
            print(f"  · Categoria já existe: {cat_name}")

    return existing


async def create_monthly_goals(
    session: AsyncSession,
    client: ClientModel,
    categories: dict[str, SpendingCategoryModel],
):
    today = date.today()
    year_month = today.replace(day=1)

    for cat_name, limit in MONTHLY_LIMITS.items():
        cat = categories.get(cat_name)
        if not cat: continue

        result = await session.execute(
            select(MonthlyGoalModel).where(
                MonthlyGoalModel.client_id == client.id,
                MonthlyGoalModel.category_id == cat.id,
                MonthlyGoalModel.year_month == year_month,
            )
        )
        if result.scalar_one_or_none():
            print(f"  · Meta já existe: {cat_name} ({year_month})")
            continue

        goal = MonthlyGoalModel(
            id=uuid4(),
            client_id=client.id,
            category_id=cat.id,
            year_month=year_month,
            limit_amount=limit,
        )
        session.add(goal)
        print(f"  ✔ Meta criada: {cat_name} → R$ {limit:.2f}")

    await session.flush()


async def create_transactions(
    session: AsyncSession,
    client: ClientModel,
    categories: dict[str, SpendingCategoryModel],
):
    today = datetime.now(tz=timezone.utc)

    for cat_name, establishment, amount, days_offset in TRANSACTIONS:
        cat = categories.get(cat_name)
        if not cat: continue

        from datetime import timedelta
        spent_at = today + timedelta(days=days_offset)

        spending = SpendingModel(
            id=uuid4(),
            client_id=client.id,
            category_id=cat.id,
            amount=amount,
            description=establishment,
            spent_at=spent_at,
        )
        session.add(spending)
        print(f"  ✔ Transação: {establishment} — R$ {amount:.2f} ({cat_name})")

    await session.flush()


async def run_seed():
    print("\n🌱 Iniciando seed do banco de dados...\n")
    
    urls_to_try = [ORIGINAL_DATABASE_URL]
    # Se o URL contém '@db:5432', adiciona fallback para 'localhost:5432'
    if "@db:5432" in ORIGINAL_DATABASE_URL:
        urls_to_try.append(ORIGINAL_DATABASE_URL.replace("@db:5432", "@localhost:5432"))

    engine = None
    for url in urls_to_try:
        try:
            print(f"📡 Tentando conectar em: {url.split('@')[1]}...")
            engine = create_async_engine(url, echo=False)
            # Testa a conexão rapidinho
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("✅ Conectado!")
            break
        except Exception:
            print(f"❌ Falha ao conectar em {url.split('@')[1]}")
            if engine: await engine.dispose()
            engine = None

    if not engine:
        print("\n🚫 Não foi possível conectar ao banco de dados em nenhum dos endereços tentados.")
        sys.exit(1)

    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            print("\n👤 Cliente:")
            client = await get_or_create_client(session)

            print("\n📂 Categorias:")
            categories = await get_or_create_categories(session)

            print("\n🎯 Metas mensais:")
            await create_monthly_goals(session, client, categories)

            print("\n💸 Transações de exemplo:")
            await create_transactions(session, client, categories)

    await engine.dispose()
    print("\n✅ Seed concluído com sucesso!")


if __name__ == "__main__":
    asyncio.run(run_seed())
