from fastapi import APIRouter, Depends, Request, BackgroundTasks
from src.infra.config import settings
from src.infra.database.session import AsyncSessionLocal
from src.api.dependencies import (
    get_webhook_parser, get_evolution_client, get_redis_session, get_gemini_client,
    get_prompt_builder
)
from src.adapters.messaging.webhook_parser import WebhookParser
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.cache.redis_session import RedisSession
from src.adapters.llm.gemini_client import GeminiClient
from src.adapters.llm.prompt_builder import PromptBuilder

from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.contribution_repository import ContributionRepositoryImpl
from src.adapters.repositories.unit_of_work import SqlAlchemyUnitOfWork

from src.use_cases.process_message import ProcessMessage

router = APIRouter(tags=["Webhook"])

async def background_process_message(phone: str, text: str):
    """
    Executa o processamento da mensagem em background, garantindo que
    cada execução tenha seu próprio ciclo de vida de sessão de banco de dados.
    Isso evita problemas com sessões fechadas pelo escopo da Request do FastAPI.
    """
    async with AsyncSessionLocal() as session:
        # Criando adaptadores com a sessão local
        uow = SqlAlchemyUnitOfWork(session)
        client_repo = ClientRepositoryImpl(session)
        spending_repo = SpendingRepositoryImpl(session)
        goal_repo = GoalRepositoryImpl(session)
        contribution_repo = ContributionRepositoryImpl(session)
        
        # Adaptadores externos (não dependem de sessão DB)
        redis_session = RedisSession()
        evolution_client = EvolutionClient()
        prompt_builder = PromptBuilder()
        gemini_client = GeminiClient(prompt_builder)
        
        use_case = ProcessMessage(
            client_repo=client_repo,
            spending_repo=spending_repo,
            goal_repo=goal_repo,
            contribution_repo=contribution_repo,
            uow=uow,
            redis_session=redis_session,
            evolution_client=evolution_client,
            gemini_client=gemini_client
        )
        
        await use_case.execute(phone, text)


@router.post("/webhook/evolution", summary="Recebe mensagens", description="Recebe mensagens da Evolution API WhatsApp")
async def evolution_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    parser: WebhookParser = Depends(get_webhook_parser)
):
    payload = await request.json()
    msg = parser.parse_upsert_message(payload)
    
    if not msg:
        return {"status": "ignored"}
        
    # Agendamos a tarefa de background usando uma função que gerencia sua própria sessão
    background_tasks.add_task(background_process_message, msg.phone, msg.text)
    
    return {"status": "ok"}


if settings.app_env == "development":
    from pydantic import BaseModel
    
    class SimulateMessageRequest(BaseModel):
        phone: str
        text: str

    @router.post("/dev/simulate-message", tags=["Dev / Testes"], summary="Simulador (DEV ONLY)")
    async def simulate_message(
        req: SimulateMessageRequest
    ):
        # Para o simulador, também usamos a versão isolada para garantir consistência
        await background_process_message(req.phone, req.text)
        return {"status": "simulated"}
