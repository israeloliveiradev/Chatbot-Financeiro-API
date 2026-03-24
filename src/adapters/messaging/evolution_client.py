import logging
import httpx
import os
import asyncio
from typing import Optional
from src.infra.config import settings

logger = logging.getLogger(__name__)

class EvolutionClient:
    def __init__(self):
        self.base_url = settings.evolution_server_url
        self.api_key = settings.evolution_api_key
        self.instance = settings.evolution_instance
        
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
        
        success = False
        last_error = None
        
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    logger.info(f"Mensagem enviada para {number} (tentativa {attempt+1})")
                    return response.json()
            except Exception as e:
                last_error = e
                logger.warning(f"Tentativa {attempt+1} falhou para {number}: {e}")
                await asyncio.sleep(1 * (attempt + 1))
        
        logger.error(f"Falha total ao enviar mensagem para {number} após 3 tentativas: {last_error}")
        if last_error is None:
            raise Exception("Erro desconhecido ao enviar mensagem")
        raise last_error

    async def send_presence(self, number: str, presence: str = "composing", delay: int = 2000):
        """
        Simula o estado de 'digitando' ou 'gravando áudio'.
        presence: 'composing' ou 'recording'
        """
        url = f"{self.base_url}/chat/sendPresence/{self.instance}"
        headers = {"apikey": self.api_key, "Content-Type": "application/json"}
        recipient = f"{number}@s.whatsapp.net" if "@" not in number else number
        
        payload = {
            "number": recipient,
            "presence": presence,
            "delay": delay
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload, headers=headers)
        except Exception as e:
            logger.warning(f"Erro ao enviar presence: {e}")

    async def send_buttons(self, number: str, title: str, description: str, buttons: list):
        """
        Envia uma mensagem com botões interativos (Schema Evolution v2).
        """
        url = f"{self.base_url}/message/sendButtons/{self.instance}"
        headers = {"apikey": self.api_key, "Content-Type": "application/json"}
        recipient = f"{number}@s.whatsapp.net" if "@" not in number else number
        
        # Formata os botões para o padrão v2 (Interactive/Reply)
        formatted_buttons = [
            {
                "type": "reply",
                "displayText": b.get("label", b.get("displayText", "Botão")),
                "id": b.get("id", str(i))
            } for i, b in enumerate(buttons)
        ]

        payload = {
            "number": recipient,
            "title": title,
            "description": description,
            "footer": "Senior Bot v2.0",
            "buttons": formatted_buttons
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(f"Erro ao enviar botões: {response.status_code} - {response.text}")
            response.raise_for_status()
            return response.json()

    async def send_document(self, number: str, file_path: str, filename: str, caption: str = ""):
        """
        Envia um documento (PDF) para o usuário.
        """
        url = f"{self.base_url}/message/sendMedia/{self.instance}"
        headers = {"apikey": self.api_key}
        recipient = f"{number}@s.whatsapp.net" if "@" not in number else number

        with open(file_path, "rb") as f:
            files = {
                "file": (filename, f, "application/pdf")
            }
            data = {
                "number": recipient,
                "mediatype": "document",
                "caption": caption,
                "fileName": filename
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=data, files=files, headers=headers)
                response.raise_for_status()
                return response.json()

    async def get_audio_transcription(self, media_url: str) -> Optional[str]:
        """
        Recupera a transcrição do áudio. 
        Nota: Se a Evolution API tiver transcrição nativa ativa, usamos ela.
        Caso contrário, baixamos e poderíamos usar um provedor de LLM configurado.
        """
        # Por enquanto, tentamos buscar o campo 'transcription' se vier no media_url (se for um objeto complexo do webhook)
        # Mas como media_url é uma string, assumimos que ProcessMessage cuidará da lógica se retornarmos None ou delegamos.
        # Simplificação: O Evolution v2 já transcreve se configurado.
        return None # Delegar para o LLM configurado no use case se necessário.

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
