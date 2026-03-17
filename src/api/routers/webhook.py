from fastapi import APIRouter, Depends, Request, BackgroundTasks
from src.infra.config import settings
from src.api.dependencies import (
    get_webhook_parser, get_evolution_client, get_redis_session, get_gemini_client,
    get_client_repository, get_spending_repository, get_goal_repository, get_contribution_repository
)
from src.adapters.messaging.webhook_parser import WebhookParser
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.cache.redis_session import RedisSession
from src.adapters.llm.gemini_client import GeminiClient
from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.contribution_repository import ContributionRepositoryImpl

from src.use_cases.process_message import ProcessMessage

router = APIRouter(tags=["Webhook"])

@router.post("/webhook/evolution", summary="Recebe mensagens", description="Recebe mensagens da Evolution API WhatsApp")
async def evolution_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    parser: WebhookParser = Depends(get_webhook_parser),
    evolution_client: EvolutionClient = Depends(get_evolution_client),
    redis_session: RedisSession = Depends(get_redis_session),
    gemini_client: GeminiClient = Depends(get_gemini_client),
    client_repo: ClientRepositoryImpl = Depends(get_client_repository),
    spending_repo: SpendingRepositoryImpl = Depends(get_spending_repository),
    goal_repo: GoalRepositoryImpl = Depends(get_goal_repository),
    contribution_repo: ContributionRepositoryImpl = Depends(get_contribution_repository)
):
    payload = await request.json()
    msg = parser.parse_upsert_message(payload)
    
    if not msg:
        return {"status": "ignored"}
        
    # Usando BackgroundTasks do FastAPI para responder o Webhook imediatamente 
    # e processar a lógica pesada (LLM/Banco) de forma assíncrona.
    use_case = ProcessMessage(
        client_repo, spending_repo, goal_repo, contribution_repo,
        redis_session, evolution_client, gemini_client
    )
    
    background_tasks.add_task(use_case.execute, msg.phone, msg.text)
    
    return {"status": "ok"}


if settings.app_env == "development":
    from pydantic import BaseModel
    
    class SimulateMessageRequest(BaseModel):
        phone: str
        text: str

    @router.post("/dev/simulate-message", tags=["Dev / Testes"], summary="Simulador (DEV ONLY)")
    async def simulate_message(
        req: SimulateMessageRequest,
        evolution_client: EvolutionClient = Depends(get_evolution_client),
        redis_session: RedisSession = Depends(get_redis_session),
        gemini_client: GeminiClient = Depends(get_gemini_client),
        client_repo: ClientRepositoryImpl = Depends(get_client_repository),
        spending_repo: SpendingRepositoryImpl = Depends(get_spending_repository),
        goal_repo: GoalRepositoryImpl = Depends(get_goal_repository),
        contribution_repo: ContributionRepositoryImpl = Depends(get_contribution_repository)
    ):
        use_case = ProcessMessage(
            client_repo, spending_repo, goal_repo, contribution_repo,
            redis_session, evolution_client, gemini_client
        )
        await use_case.execute(req.phone, req.text)
        return {"status": "simulated"}
