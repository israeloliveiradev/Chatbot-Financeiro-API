import logging
from typing import List, Dict, Any, Optional

import google.generativeai as genai
from google.generativeai.types import content_types
from pydantic import BaseModel
import os

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, prompt_builder=None, tools=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY não configurada")
            raise ValueError("GEMINI_API_KEY não configurada")
        
        genai.configure(api_key=api_key)
        self.prompt_builder = prompt_builder
        self.model = genai.GenerativeModel('gemini-1.5-flash', tools=tools)
        
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    async def analyze_message(self, prompt: str, history: List[Dict[str, str]] = None) -> str:
        """
        Analisa a mensagem do usuário usando o Gemini 1.5.
        Retorna a resposta do modelo (geralmente um JSON formatado).
        """
        chat = self.model.start_chat(history=[])
        
        # Converte o histórico para o formato do Gemini se necessário
        # (Para o MVP, estamos enviando o histórico completo no prompt do sistema via PromptBuilder)
        
        try:
            # BUG-01 FIX: Usar send_message_async e await
            response = await chat.send_message_async(
                prompt,
                safety_settings=self.safety_settings
            )
            return response.text
        except Exception as e:
            logger.error(f"Erro ao chamar Gemini: {e}")
            raise

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Transcreve um áudio usando as capacidades multimodais do Gemini.
        """
        try:
            # Gemini 1.5 suporta áudio diretamente como parte do conteúdo
            contents = [
                {
                    "mime_type": mime_type,
                    "data": audio_bytes
                },
                "Transcreva exatamente o que foi dito neste áudio. Retorne apenas o texto transcrito, sem comentários adicionais."
            ]
            response = await self.model.generate_content_async(contents)
            return response.text
        except Exception as e:
            logger.error(f"Erro na transcrição de áudio: {e}")
            return ""
