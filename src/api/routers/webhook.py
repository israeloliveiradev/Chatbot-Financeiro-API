from fastapi import APIRouter, Depends, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
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
from src.infra.logging import get_logger

logger = get_logger(__name__)

from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.contribution_repository import ContributionRepositoryImpl
from src.adapters.repositories.unit_of_work import SqlAlchemyUnitOfWork

from src.adapters.llm.tools import FINANCIAL_TOOLS
from src.use_cases.process_message import ProcessMessage

router = APIRouter(prefix="/webhook", tags=["Webhook"])

class SimulateMessageRequest(BaseModel):
    phone: str
    text: str

async def background_process_message(phone: str, text: str, message_id: Optional[str] = None, is_audio: bool = False, media_url: Optional[str] = None):
    """
    Executa o processamento da mensagem em background com suporte a áudio.
    """
    async with AsyncSessionLocal() as session:
        uow = SqlAlchemyUnitOfWork(session)
        client_repo = ClientRepositoryImpl(session)
        spending_repo = SpendingRepositoryImpl(session)
        goal_repo = GoalRepositoryImpl(session)
        contribution_repo = ContributionRepositoryImpl(session)
        
        redis_session = RedisSession()
        evolution_client = EvolutionClient()
        prompt_builder = PromptBuilder()
        gemini_client = GeminiClient(prompt_builder, tools=FINANCIAL_TOOLS)
        
        use_case = ProcessMessage(
            uow=uow,
            client_repo=client_repo,
            goal_repo=goal_repo,
            spending_repo=spending_repo,
            contribution_repo=contribution_repo,
            gemini_client=gemini_client,
            evolution_client=evolution_client,
            prompt_builder=prompt_builder
        )
        
        await use_case.execute(phone=phone, text=text, message_id=message_id, is_audio=is_audio, media_url=media_url)


@router.post("/evolution")
async def evolution_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    parser: WebhookParser = Depends(get_webhook_parser)
):
    """
    Recebe webhooks da Evolution API.
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}
    
    event = data.get("event", "")
    instance = data.get("instance")
    
    logger.info(f"[WEBHOOK] Event: {event}, Instance: {instance}")
    
    # Validação de Instância
    if instance != settings.evolution_instance:
        return {"status": "ignored", "reason": "invalid_instance"}
    
    # Ignorar eventos que não são mensagens novas (retornar 200 para evitar retry!)
    if event != "messages.upsert":
        return {"status": "ignored", "reason": f"event_{event}"}
    
    # Parsear mensagem
    message = parser.parse_message(data)
    if not message:
        return {"status": "ignored"}
    
    logger.info(f"[WEBHOOK] Processing message from {message.phone}: {message.text[:50]}")
    
    background_tasks.add_task(
        background_process_message,
        phone=message.phone,
        text=message.text,
        message_id=message.message_id,
        is_audio=message.is_audio,
        media_url=message.media_url
    )
    
    return {"status": "queued"}


@router.post("/dev/simulate-message", tags=["Dev / Testes"], summary="Simulador (DEV ONLY)")
async def simulate_message(
    req: SimulateMessageRequest
):
    """Simula uma mensagem para testes rápidos."""
    await background_process_message(req.phone, req.text)
    return {"status": "simulated"}
