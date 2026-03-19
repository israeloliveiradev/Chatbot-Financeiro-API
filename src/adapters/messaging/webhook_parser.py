import base64
import logging
from typing import Dict, Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WebhookMessage(BaseModel):
    phone: str
    text: str
    message_id: str
    push_name: str | None = None
    # Suporte a mensagens de áudio
    audio_base64: str | None = None
    audio_mimetype: str | None = None
    media_url: str | None = None

    @property
    def is_audio(self) -> bool:
        return self.audio_base64 is not None or self.media_url is not None

    def get_audio_bytes(self) -> bytes | None:
        if self.audio_base64:
            # Linter fix: cast to str or use explicit check
            return base64.b64decode(str(self.audio_base64))
        return None


class WebhookParser:
    def parse_message(self, payload: Dict[str, Any]) -> Optional[WebhookMessage]:
        """
        Parseia o payload do webhook de 'messages.upsert' da Evolution API v2.
        Suporta mensagens de texto e áudio.
        Retorna None se for mensagem própria, de grupo, ou evento irrelevante.
        """
        event = payload.get("event")
        if event != "messages.upsert":
            return None

        data = payload.get("data", {})
        key = data.get("key", {})

        # Ignorar mensagens enviadas pelo próprio bot
        if key.get("fromMe") is True:
            return None

        remote_jid = key.get("remoteJid", "")
        # Ignorar mensagens de grupo
        if "@g.us" in remote_jid:
            return None

        message_id = key.get("id")
        message = data.get("message", {})

        text = ""
        audio_base64 = None
        audio_mimetype = None
        media_url = None

        # Texto simples
        if "conversation" in message:
            text = message["conversation"]
        # Texto com resposta/formatação especial
        elif "extendedTextMessage" in message:
            text = message["extendedTextMessage"].get("text", "")
        # Mensagem de áudio (audioMessage na Evolution API v2)
        elif "audioMessage" in message:
            audio_msg = message["audioMessage"]
            audio_base64 = audio_msg.get("base64")
            media_url = audio_msg.get("url") or data.get("mediaUrl") or data.get("url")
            audio_mimetype = audio_msg.get("mimetype", "audio/ogg; codecs=opus")

            if not audio_base64 and not media_url:
                logger.warning("Mensagem de áudio recebida sem base64 ou URL. message_id=%s", message_id)
                return None

        if not text and not audio_base64 and not media_url:
            return None

        push_name = data.get("pushName")
        phone = remote_jid.split("@")[0].split(":")[0]

        return WebhookMessage(
            phone=phone,
            text=str(text),
            message_id=str(message_id),
            push_name=push_name,
            audio_base64=audio_base64,
            audio_mimetype=audio_mimetype,
            media_url=media_url
        )
