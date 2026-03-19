import logging
import httpx
import os
from typing import Optional

logger = logging.getLogger(__name__)

class EvolutionClient:
    def __init__(self):
        self.base_url = os.getenv("EVOLUTION_BASE_URL", "http://evolution:8080")
        self.api_key = os.getenv("EVOLUTION_API_KEY")
        self.instance = os.getenv("EVOLUTION_INSTANCE", "MainInstance")
        
        if not self.api_key:
            logger.error("EVOLUTION_API_KEY não configurada")
            raise ValueError("EVOLUTION_API_KEY não configurada")

    async def send_text_message(self, number: str, text: str):
        """
        Envia uma mensagem de texto via Evolution API.
        """
        url = f"{self.base_url}/message/sendText/{self.instance}"
        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }
        # Garantir que o número tenha o formato JID se for apenas dígitos
        recipient = number
        if "@" not in recipient:
            recipient = f"{recipient}@s.whatsapp.net"

        payload = {
            "number": recipient,
            "text": text,
            "delay": 1200,
            "linkPreview": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                logger.info(f"Mensagem enviada para {number}")
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP ao enviar mensagem: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Erro de rede ao enviar mensagem: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar mensagem para {number}: {e}")
            raise

    async def download_media(self, media_url: str) -> Optional[bytes]:
        """
        Faz o download de um arquivo de mídia (áudio, imagem, etc) da Evolution API.
        """
        headers = {
            "apikey": self.api_key
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(media_url, headers=headers)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Erro ao baixar mídia da Evolution ({media_url}): {e}")
            return None
