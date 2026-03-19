import json
import logging
from typing import Dict, Any, List

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tenacity import retry, stop_after_attempt, wait_exponential

from src.infra.config import settings
from src.infra.logging import get_logger
from src.adapters.llm.prompt_builder import PromptBuilder

logger = get_logger(__name__)

class GeminiClient:
    def __init__(self, prompt_builder: PromptBuilder, tools: List[Any] = None):
        self.prompt_builder = prompt_builder
        self.tools = tools
        genai.configure(api_key=settings.gemini_api_key)
        
        # Configure model parameters
        self.generation_config = {
            "temperature": 0.1, # Lower temperature for better tool calling
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 1024,
        }
        
        # Safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
            tools=self.tools,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying Gemini API call (attempt {retry_state.attempt_number})..."
        )
    )
    async def chat(
        self, 
        system_instruction: str,
        history: List[Dict[str, str]], 
        message: str
    ) -> Any:
        """
        Inicia ou continua um chat enviando a mensagem e capturando a resposta.
        Retorna a tupla (response, chat_session) para permitir follow-ups de Tool Calls.
        """
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
            tools=self.tools, # Reuse configured tools
            system_instruction=system_instruction
        )

        formatted_history = []
        for msg in history:
            formatted_history.append({
                "role": "model" if msg["role"] == "assistant" else "user",
                "parts": [msg["content"]]
            })
            
        chat_session = model.start_chat(history=formatted_history)
        response = chat_session.send_message(message)
        
        # Log de Uso (Otimização de Custos)
        try:
            usage = response.usage_metadata
            logger.info(f"Gemini Usage: Prompt={usage.prompt_token_count}, Model={usage.candidates_token_count}, Total={usage.total_token_count}")
        except Exception as e:
            logger.warning(f"Não foi possível extrair metadados de uso: {e}")
            
        return response, chat_session

    async def send_tool_response(self, chat_session: Any, tool_name: str, result: Dict[str, Any]) -> Any:
        """
        Envia o resultado da execução da ferramenta de volta para a sessão ativa do Gemini
        para que ele possa gerar a resposta final humanizada.
        Usa genai.protos.Part que é compatível com SDK >= 0.7.x
        """
        tool_response_part = genai.protos.Part(
            function_response=genai.protos.FunctionResponse(
                name=tool_name,
                response={"result": result.get("result", str(result))}
            )
        )
        response = chat_session.send_message(tool_response_part)
        return response

    async def transcribe_audio(self, audio_data: bytes, mime_type: str = "audio/mp3") -> str:
        """
        Usa o Gemini para transcrever um áudio binário.
        """
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content([
                "Transcreva este áudio financeiro exatamente como dito pelo usuário. Responda apenas com a transcrição.",
                {
                    "mime_type": mime_type,
                    "data": audio_data
                }
            ])
            return response.text.strip()
        except Exception as e:
            logger.error(f"Erro na transcrição Gemini: {e}")
            return "[Erro na transcrição]"
