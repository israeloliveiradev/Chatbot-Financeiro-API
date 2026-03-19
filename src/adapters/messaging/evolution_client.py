import httpx
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from src.infra.config import settings
from src.infra.logging import get_logger

logger = get_logger(__name__)

class EvolutionClient:
    def __init__(self):
        self.base_url = settings.evolution_base_url.rstrip("/")
        self.instance = settings.evolution_instance
        self.api_key = settings.evolution_api_key
        
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying Evolution API call (attempt {retry_state.attempt_number})..."
        )
    )
    async def send_text_message(self, phone: str, text: str) -> Dict[str, Any]:
        """
        Envia uma mensagem de texto para o cliente vi WhatsApp usando a Evolution API.
        """
        if not text or not str(text).strip():
            logger.warning(f"Tentativa de enviar mensagem de texto vazia para o numero {phone} ignorada.")
            return {"status": "error", "message": "Texto vazio ou invalido"}

        url = f"{self.base_url}/message/sendText/{self.instance}"
        
        payload = {
            "number": phone,
            "text": text
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                try:
                    error_json = e.response.json()
                    logger.error(f"Evolution API HTTP {e.response.status_code}: {error_json}")
                    return {"status": "error", "message": error_json}
                except Exception:
                    logger.error(f"Evolution API HTTP {e.response.status_code}: {e.response.text}")
                    return {"status": "error", "message": str(e)}
    async def download_media(self, message_id: str, media_url: str = None) -> bytes:
        """
        Faz o download do binário de uma mídia (áudio, imagem, etc).
        Tenta primeiro via Evolution API v2 (getBase64FromMediaMessage).
        Se falhar ou media_url for fornecida, baixa diretamente da URL do WhatsApp CDN.
        """
        # Tenta via Evolution API v2
        url = f"{self.base_url}/chat/getBase64FromMediaMessage/{self.instance}"
        
        payload = {
            "message": {"key": {"id": message_id}},
            "convertToMp3": True
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                import base64
                base64_data = data.get("base64") or data.get("data")
                if base64_data:
                    return base64.b64decode(base64_data.split(",")[-1])
        except Exception as e:
            logger.warning(f"Evolution API download falhou ({e}), tentando URL direta...")
        
        # Fallback: baixar diretamente da URL do CDN do WhatsApp
        if media_url:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(media_url)
                response.raise_for_status()
                return response.content
        
        raise ValueError(f"Não foi possível baixar a mídia da mensagem {message_id}")

