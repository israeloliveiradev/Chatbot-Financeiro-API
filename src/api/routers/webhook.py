import json
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from src.infra.config import settings
from src.infra.database.session import AsyncSessionLocal
from src.api.dependencies import (
    get_webhook_parser, create_process_message_from_session
)
from src.infra.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])

class SimulateMessageRequest(BaseModel):
    phone: str
    text: str

async def background_process_message(
    phone: str,
    text: str,
    message_id: Optional[str] = None,
    is_audio: bool = False,
    media_url: Optional[str] = None
):
    """
    Executa o processamento da mensagem em background com suporte a áudio.
    """
    async with AsyncSessionLocal() as session:
        # Usa a factory centralizada para criar o caso de uso
        use_case = create_process_message_from_session(session)

        await use_case.execute(
            phone=phone,
            text=text,
            message_id=message_id,
            is_audio=is_audio,
            media_url=media_url
        )

@router.post("/evolution")
async def evolution_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    parser = Depends(get_webhook_parser)
):
    """
    Recebe webhooks da Evolution API.
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    # DEBUG: logar payload completo para descobrir onde está o número real
    logger.info(f"[WEBHOOK DEBUG] Payload completo: {json.dumps(data, indent=2, default=str)}")

    event = data.get("event", "")
    instance = data.get("instance")

    logger.info(f"[WEBHOOK] Event: {event}, Instance: {instance}")

    # Validação de Instância
    if instance != settings.evolution_instance:
        return {"status": "ignored", "reason": "invalid_instance"}

    # Ignorar eventos que não são mensagens novas
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
