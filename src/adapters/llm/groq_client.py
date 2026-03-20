import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from src.infra.config import settings
from src.adapters.llm.base import LLMClient

logger = logging.getLogger(__name__)

# Mapeamento tool name → intent do process_message (Igual ao Gemini)
_TOOL_TO_INTENT = {
    "criar_objetivo": "criar_objetivo",
    "registrar_gasto": "registrar_gasto",
    "registrar_aporte": "registrar_aporte",
    "simular_poupanca": "simular_poupanca",
    "cancelar_objetivo": "cancelar_objetivo",
    "listar_objetivos": "listar_objetivos",
    "definir_meta_mensal": "definir_meta_mensal",
    "obter_resumo_mensal": "obter_resumo_mensal",
    "simular_compra": "simular_compra",
    "gerar_relatorio": "gerar_relatorio",
    "responder_conversa": "conversa",
}

class GroqLLMClient(LLMClient):
    def __init__(self, prompt_builder=None, tools=None):
        self.api_key = settings.groq_api_key
        self.model_name = settings.groq_model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.transcribe_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        self.prompt_builder = prompt_builder
        self.tools_list = tools # Guardamos para o prompt

    def _get_system_prompt(self) -> str:
        """Constrói o system prompt com as ferramentas disponíveis."""
        tools_desc = ""
        if self.tools_list:
            for fn in self.tools_list:
                tools_desc += f"- {fn.__name__}: {fn.__doc__.strip() if fn.__doc__ else ''}\n"

        return f"""Você é um assistente financeiro inteligente e amigável.
Sua tarefa é analisar a mensagem do usuário e decidir qual ferramenta usar ou se deve apenas responder à conversa.

FERRAMENTAS DISPONÍVEIS:
{tools_desc}

REGRAS:
1. Se a mensagem for um comando para uma ferramenta, extraia os dados necessários.
2. Se for uma dúvida geral ou saudação, use a ferramenta 'responder_conversa'.
3. Retorne SEMPRE um JSON válido no seguinte formato:
{{
  "intent": "nome_da_ferramenta",
  "extracted_data": {{ "param1": "valor1", ... }},
  "reply_text": "Mensagem amigável para o usuário (obrigatório apenas se intent for 'conversa')"
}}

Mapeamento de Intent:
- responder_conversa -> intent: 'conversa'
- registrar_gasto -> intent: 'registrar_gasto'
- criar_objetivo -> intent: 'criar_objetivo'
- (use o nome da função como intent, exceto para responder_conversa)
"""

    async def analyze_message(self, system_prompt: str, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Injetamos as instruções técnicas de JSON no system prompt
        full_system_prompt = f"{system_prompt}\n\n{self._get_system_instructions()}"

        messages = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)
                
                # Normalização mínima
                if "intent" not in result: result["intent"] = "conversa"
                if "extracted_data" not in result: result["extracted_data"] = {}
                if result["intent"] == "responder_conversa": result["intent"] = "conversa"

                return json.dumps(result, ensure_ascii=False)
                
            except Exception as e:
                logger.error(f"[LLM-GROQ] Erro ao chamar Groq: {e}")
                return json.dumps({
                    "intent": "conversa",
                    "extracted_data": {},
                    "reply_text": "Desculpe, tive um problema ao processar via Groq. 😅"
                }, ensure_ascii=False)
        
        return json.dumps({
            "intent": "conversa",
            "extracted_data": {},
            "reply_text": "Erro inesperado ao processar mensagem. 😅"
        }, ensure_ascii=False)

    def _get_system_instructions(self) -> str:
        """Instruções técnicas de formato para o Groq."""
        return """
Sua tarefa é analisar a mensagem do usuário e decidir qual ferramenta usar.
Retorne SEMPRE um JSON válido no seguinte formato:
{
  "intent": "nome_da_ferramenta",
  "extracted_data": { "param1": "valor1", ... },
  "reply_text": "Mensagem amigável para o usuário (obrigatório apenas se intent for 'conversa')"
}
Mapeamento: responder_conversa -> intent: 'conversa'.
"""

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Transcreve áudio usando Groq Whisper com melhor tratamento de erro.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # WhatsApp costuma enviar ogg/opus. Groq é sensível à extensão.
        # Se vier algo com ogg/opus, chamamos de .ogg. Caso contrário, .mp3 como fallback seguro.
        ext = "ogg" if "ogg" in mime_type.lower() or "opus" in mime_type.lower() else "mp3"
        filename = f"audio.{ext}"
        
        files = {
            "file": (filename, audio_bytes, mime_type),
        }
        data = {
            "model": "whisper-large-v3-turbo",
            "language": "pt",
            "response_format": "json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.transcribe_url, 
                    headers=headers, 
                    files=files, 
                    data=data, 
                    timeout=60.0
                )
                if response.status_code != 200:
                    logger.error(f"[LLM-GROQ] Erro 400+ na Transcrição: {response.text}")
                response.raise_for_status()
                
                result = response.json()
                text = result.get("text", "").strip()
                logger.info(f"[LLM-GROQ] Transcrição concluída: {text[:50]}...")
                return text
            except Exception as e:
                logger.error(f"[LLM-GROQ] Falha total na transcrição: {e}")
                return ""
        
        return ""

    async def generate_response(self, prompt: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=payload, timeout=30.0)
                data = response.json()
                return {"reply_text": data["choices"][0]["message"]["content"]}
            except Exception as e:
                logger.error(f"Erro em Groq generate_response: {e}")
                return {"reply_text": ""}
        return {"reply_text": ""}
