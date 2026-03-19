from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.session import get_db_session
from src.adapters.cache.redis_session import RedisSession
from src.adapters.llm.gemini_client import GeminiClient
from src.adapters.llm.prompt_builder import PromptBuilder
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.messaging.webhook_parser import WebhookParser

from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.contribution_repository import ContributionRepository
from src.domain.repositories.unit_of_work import UnitOfWork

from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.contribution_repository import ContributionRepositoryImpl
from src.adapters.repositories.unit_of_work import SqlAlchemyUnitOfWork

# DB Repositories
def get_client_repository(session: AsyncSession = Depends(get_db_session)) -> ClientRepository:
    return ClientRepositoryImpl(session)

def get_goal_repository(session: AsyncSession = Depends(get_db_session)) -> GoalRepository:
    return GoalRepositoryImpl(session)

def get_spending_repository(session: AsyncSession = Depends(get_db_session)) -> SpendingRepository:
    return SpendingRepositoryImpl(session)

def get_contribution_repository(session: AsyncSession = Depends(get_db_session)) -> ContributionRepository:
    return ContributionRepositoryImpl(session)

def get_unit_of_work(session: AsyncSession = Depends(get_db_session)) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)

from src.adapters.llm.tools import FINANCIAL_TOOLS

# External Adapters
def get_redis_session() -> RedisSession:
    return RedisSession()

def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()

def get_gemini_client(prompt_builder: PromptBuilder = Depends(get_prompt_builder)) -> GeminiClient:
    return GeminiClient(prompt_builder, tools=FINANCIAL_TOOLS)

def get_evolution_client() -> EvolutionClient:
    return EvolutionClient()

def get_webhook_parser() -> WebhookParser:
    return WebhookParser()
