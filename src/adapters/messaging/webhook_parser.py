from typing import Dict, Any, Optional
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class WebhookMessage(BaseModel):
    phone: str
    text: str | None = None
    is_audio: bool = False
    media_url: str | None = None
    message_id: str
    push_name: str | None = None

class WebhookParser:
    def parse_upsert_message(self, payload: Dict[str, Any]) -> Optional[WebhookMessage]:
        """
        Parseia o payload do webhook de 'messages.upsert' da Evolution API v2.
        """
        event = payload.get("event")
        if event != "messages.upsert":
            return None
            
        data = payload.get("data", {})
        key = data.get("key", {})
        
        if key.get("fromMe") is True:
            return None
            
        remote_jid = key.get("remoteJid", "")
        logger.info(f"Webhook event recebido. JID original: {remote_jid}")
        
        # Ignorar Grupos, Canais e Status
        if "@g.us" in remote_jid or "@newsletter" in remote_jid or "@broadcast" in remote_jid:
            return None
            
        message_id = key.get("id")
        message = data.get("message", {})
        
        text = None
        is_audio = False
        media_url = None
        
        # Texto Simples
        if "conversation" in message:
            text = message["conversation"]
        elif "extendedTextMessage" in message:
            text = message["extendedTextMessage"].get("text", "")
        
        # Áudio
        elif "audioMessage" in message:
            is_audio = True
            text = "[Mensagem de Áudio]"
            media_url = message["audioMessage"].get("url")
            
        if not text and not is_audio:
            return None
            
        remote_jid_alt = key.get("remoteJidAlt", "")
        best_jid = remote_jid
        
        if "@s.whatsapp.net" in remote_jid_alt:
            best_jid = remote_jid_alt
        elif "@s.whatsapp.net" in remote_jid:
            best_jid = remote_jid
            
        phone = best_jid.split("@")[0]
        push_name = data.get("pushName")
        
        return WebhookMessage(
            phone=phone,
            text=text,
            is_audio=is_audio,
            message_id=message_id,
            push_name=push_name
        )
