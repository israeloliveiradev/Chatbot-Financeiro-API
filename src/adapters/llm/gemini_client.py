import json
from typing import Dict, Any, List

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from src.infra.config import settings
from src.adapters.llm.prompt_builder import PromptBuilder

class GeminiClient:
    def __init__(self, prompt_builder: PromptBuilder):
        self.prompt_builder = prompt_builder
        genai.configure(api_key=settings.gemini_api_key)
        
        # Configure model parameters
        self.generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
        }
        
        # Safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
        )

    async def analyze_message(
        self, 
        system_prompt: str, 
        history: List[Dict[str, str]], 
        current_message: str
    ) -> Dict[str, Any]:
        """
        Envia a mensagem atual junto com o histórico e instruções de sistema para o Gemini.
        Espera um JSON de resposta ditado pela configuração.
        """
        
        formatted_history = []
        for msg in history:
            formatted_history.append({
                "role": "model" if msg["role"] == "assistant" else "user",
                "parts": [msg["content"]]
            })
            
        chat = self.model.start_chat(history=formatted_history)
        
        # O system_prompt é anexado à mensagem atual para reforçar o contexto JSON a cada turno
        full_message = f"{system_prompt}\n\nMENSAGEM DO USUÁRIO:\n{current_message}"
        
        response = chat.send_message(full_message)
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback for unexpected format
            return {
                "intent": "desconhecido",
                "extracted_data": {},
                "response": "Desculpe, tive um problema ao interpretar sua mensagem."
            }
