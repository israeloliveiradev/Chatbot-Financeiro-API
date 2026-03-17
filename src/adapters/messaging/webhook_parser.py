from typing import Dict, Any, Optional
from pydantic import BaseModel

class WebhookMessage(BaseModel):
    phone: str
    text: str
    message_id: str
    push_name: str | None = None

class WebhookParser:
    def parse_upsert_message(self, payload: Dict[str, Any]) -> Optional[WebhookMessage]:
        """
        Parseia o payload do webhook de 'messages.upsert' da Evolution API v2.
        Retorna um WebhookMessage se for uma mensagem válida de texto recebida.
        Retorna None se for uma mensagem enviada por nós (fromMe=True), evento irrelevante, etc.
        """
        event = payload.get("event")
        if event != "messages.upsert":
            return None
            
        data = payload.get("data", {})
        key = data.get("key", {})
        
        # Ignorar mensagens enviadas pelo próprio bot ou pelo logado na mesma interface
        if key.get("fromMe") is True:
            return None
            
        remote_jid = key.get("remoteJid", "")
        # Ignorar mensagens de grupo
        if "@g.us" in remote_jid:
            return None
            
        message_id = key.get("id")
        
        # Extrai o texto da mensagem
        message = data.get("message", {})
        text = ""
        
        # A API pode mandar de duas formas dependendo do tipo (texto simples ou quoted/extended)
        if "conversation" in message:
            text = message["conversation"]
        elif "extendedTextMessage" in message:
            text = message["extendedTextMessage"].get("text", "")
            
        if not text:
            return None
            
        # Extrai o nome e o telefone limpo
        push_name = data.get("pushName")
        phone = remote_jid.split("@")[0]
        
        return WebhookMessage(
            phone=phone,
            text=text,
            message_id=message_id,
            push_name=push_name
        )
