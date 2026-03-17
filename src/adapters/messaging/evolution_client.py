import httpx
from typing import Dict, Any

from src.infra.config import settings

class EvolutionClient:
    def __init__(self):
        self.base_url = settings.evolution_base_url.rstrip("/")
        self.instance = settings.evolution_instance
        self.api_key = settings.evolution_api_key
        
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }

    async def send_text_message(self, phone: str, text: str) -> Dict[str, Any]:
        """
        Envia uma mensagem de texto para o cliente vi WhatsApp usando a Evolution API.
        """
        url = f"{self.base_url}/message/sendText/{self.instance}"
        
        payload = {
            "number": phone,
            "text": text
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
