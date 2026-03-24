from typing import AsyncGenerator, Any
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database.session import get_db_session
from src.adapters.cache.redis_session import RedisSession
from src.adapters.llm.prompt_builder import PromptBuilder
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.messaging.webhook_parser import WebhookParser
from src.adapters.llm.base import LLMClient
from src.adapters.llm.gemini_client import GeminiLLMClient
from src.adapters.llm.groq_client import GroqLLMClient
from src.infra.config import settings

from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.contribution_repository import ContributionRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.services.proactive_alerter import ProactiveAlerter

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

def get_llm_client(prompt_builder: PromptBuilder = Depends(get_prompt_builder)) -> LLMClient:
    if settings.llm_provider == "groq":
        return GroqLLMClient(prompt_builder, tools=FINANCIAL_TOOLS)
    return GeminiLLMClient(prompt_builder, tools=FINANCIAL_TOOLS)

def get_evolution_client() -> EvolutionClient:
    return EvolutionClient()

def get_webhook_parser() -> WebhookParser:
    return WebhookParser()

# Services
def get_proactive_alerter(
    spending_repo: SpendingRepository = Depends(get_spending_repository),
    evolution_client: EvolutionClient = Depends(get_evolution_client)
) -> ProactiveAlerter:
    return ProactiveAlerter(spending_repo, evolution_client)

from src.use_cases.process_message import ProcessMessage
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_goals import GetGoals
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.use_cases.register_spending import RegisterSpending
from src.use_cases.create_goal import CreateGoal
from src.use_cases.register_contribution import RegisterContribution

# Use Case Factories
def get_get_client_use_case(repo: ClientRepository = Depends(get_client_repository)) -> GetClientByPhone:
    return GetClientByPhone(repo)

def get_get_goals_use_case(repo: GoalRepository = Depends(get_goal_repository)) -> GetGoals:
    return GetGoals(repo)

def get_get_monthly_spending_use_case(repo: SpendingRepository = Depends(get_spending_repository)) -> GetMonthlySpending:
    return GetMonthlySpending(repo)

def get_register_spending_use_case(repo: SpendingRepository = Depends(get_spending_repository)) -> RegisterSpending:
    return RegisterSpending(repo)

def get_create_goal_use_case(repo: GoalRepository = Depends(get_goal_repository)) -> CreateGoal:
    return CreateGoal(repo)

def get_register_contribution_use_case(
    contribution_repo: ContributionRepository = Depends(get_contribution_repository),
    goal_repo: GoalRepository = Depends(get_goal_repository)
) -> RegisterContribution:
    return RegisterContribution(contribution_repo, goal_repo)

def create_process_message_from_session(session: AsyncSession) -> ProcessMessage:
    """
    Cria uma instância completa do ProcessMessage a partir de uma sessão.
    Útil para tarefas em background onde o Depends() não é aplicável.
    """
    uow = SqlAlchemyUnitOfWork(session)
    client_repo = ClientRepositoryImpl(session)
    spending_repo = SpendingRepositoryImpl(session)
    goal_repo = GoalRepositoryImpl(session)
    contribution_repo = ContributionRepositoryImpl(session)
    
    prompt_builder = PromptBuilder()
    evolution_client = EvolutionClient()
    
    # LLM Client
    if settings.llm_provider == "groq":
        llm_client = GroqLLMClient(prompt_builder, tools=FINANCIAL_TOOLS)
    else:
        llm_client = GeminiLLMClient(prompt_builder, tools=FINANCIAL_TOOLS)
        
    alerter = ProactiveAlerter(spending_repo, evolution_client)
    
    # Use Cases
    return ProcessMessage(
        uow=uow,
        client_repo=client_repo,
        llm_client=llm_client,
        evolution_client=evolution_client,
        prompt_builder=prompt_builder,
        proactive_alerter=alerter,
        get_client_use_case=GetClientByPhone(client_repo),
        get_goals_use_case=GetGoals(goal_repo),
        get_monthly_spending_use_case=GetMonthlySpending(spending_repo),
        register_spending_use_case=RegisterSpending(spending_repo),
        create_goal_use_case=CreateGoal(goal_repo),
        register_contribution_use_case=RegisterContribution(contribution_repo, goal_repo)
    )

def get_process_message(
    uow: UnitOfWork = Depends(get_unit_of_work),
    client_repo: ClientRepository = Depends(get_client_repository),
    llm_client: LLMClient = Depends(get_llm_client),
    evolution_client: EvolutionClient = Depends(get_evolution_client),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    proactive_alerter: ProactiveAlerter = Depends(get_proactive_alerter),
    # Use Cases Injetados
    get_client_uc: GetClientByPhone = Depends(get_get_client_use_case),
    get_goals_uc: GetGoals = Depends(get_get_goals_use_case),
    get_monthly_spending_uc: GetMonthlySpending = Depends(get_get_monthly_spending_use_case),
    register_spending_uc: RegisterSpending = Depends(get_register_spending_use_case),
    create_goal_uc: CreateGoal = Depends(get_create_goal_use_case),
    register_contribution_uc: RegisterContribution = Depends(get_register_contribution_use_case),
) -> ProcessMessage:
    return ProcessMessage(
        uow=uow,
        client_repo=client_repo,
        llm_client=llm_client,
        evolution_client=evolution_client,
        prompt_builder=prompt_builder,
        proactive_alerter=proactive_alerter,
        get_client_use_case=get_client_uc,
        get_goals_use_case=get_goals_uc,
        get_monthly_spending_use_case=get_monthly_spending_uc,
        register_spending_use_case=register_spending_uc,
        create_goal_use_case=create_goal_uc,
        register_contribution_use_case=register_contribution_uc,
    )
