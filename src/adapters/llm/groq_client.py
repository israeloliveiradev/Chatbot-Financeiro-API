import json
import logging
import httpx
import inspect
from typing import List, Dict, Any, Optional
from src.infra.config import settings
from src.adapters.llm.base import LLMClient

logger = logging.getLogger(__name__)

# Mapeamento tool name → intent do process_message
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
        self.tools_list = tools
        self._openai_tools = self._build_openai_tools()

    def _build_openai_tools(self) -> List[Dict[str, Any]]:
        """Converte funções Python para JSON Schema (OpenAI Format)."""
        if not self.tools_list:
            return []
            
        openai_tools = []
        for fn in self.tools_list:
            # Extrair docstring para descrição
            doc = fn.__doc__ or ""
            desc = doc.split(":param")[0].strip()
            
            # Extrair parâmetros
            sig = inspect.signature(fn)
            properties = {}
            required = []
            
            for name, param in sig.parameters.items():
                # Mapeamento básico de tipos Python para JSON Schema
                p_type = "string"
                if param.annotation == float or "float" in str(param.annotation):
                    p_type = "number"
                elif param.annotation == int:
                    p_type = "integer"
                elif param.annotation == bool:
                    p_type = "boolean"
                
                # Buscar descrição do parâmetro no docstring (simplificado)
                p_desc = ""
                for line in doc.split("\n"):
                    if f":param {name}:" in line:
                        p_desc = line.split(f":param {name}:")[1].strip()
                
                properties[name] = {
                    "type": p_type,
                    "description": p_desc
                }
                
                if param.default == inspect.Parameter.empty:
                    required.append(name)
            
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": fn.__name__,
                    "description": desc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        return openai_tools

    async def analyze_message(self, system_prompt: str, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.0, # Zero para máxima previsibilidade em ferramentas
            "tools": self._openai_tools,
            "tool_choice": "auto"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                message = data["choices"][0]["message"]
                
                # Se o modelo chamou uma ferramenta
                if message.get("tool_calls"):
                    tool_call = message["tool_calls"][0]["function"]
                    name = tool_call["name"]
                    args = json.loads(tool_call["arguments"])
                    
                    intent = _TOOL_TO_INTENT.get(name, "conversa")
                    
                    # Se for responder_conversa, extraímos o reply_text
                    reply_text = args.get("reply_text", "")
                    
                    result = {
                        "intent": intent,
                        "extracted_data": args,
                        "reply_text": reply_text
                    }
                    logger.info(f"[LLM-GROQ] Tool Call: {name} | Args: {args}")
                    return json.dumps(result, ensure_ascii=False)
                
                # Fallback: Se não chamou ferramenta, mas retornou texto
                content = message.get("content", "")
                logger.warning(f"[LLM-GROQ] Sem tool_call, conteúdo: {content}")
                
                return json.dumps({
                    "intent": "conversa",
                    "extracted_data": {},
                    "reply_text": content or "Como posso ajudar? 😊"
                }, ensure_ascii=False)
                
            except Exception as e:
                logger.error(f"[LLM-GROQ] Erro ao chamar Groq: {e}")
                return json.dumps({
                    "intent": "conversa",
                    "extracted_data": {},
                    "reply_text": "Desculpe, tive um problema ao processar seu pedido. 😅"
                }, ensure_ascii=False)

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """
        Transcreve áudio usando Groq Whisper.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # Extensão baseada no mime_type
        ext = "ogg" if "ogg" in mime_type.lower() or "opus" in mime_type.lower() else "mp3"
        filename = f"audio.{ext}"
        
        files = {
            "file": (filename, audio_bytes, mime_type),
        }
        data = {
            "model": "whisper-large-v3",
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
                    logger.error(f"[LLM-GROQ] Erro na transcrição ({response.status_code}): {response.text}")
                response.raise_for_status()
                
                result = response.json()
                text = result.get("text", "").strip()
                return text
            except Exception as e:
                logger.error(f"[LLM-GROQ] Falha na transcrição: {e}")
                return ""

    async def generate_response(self, prompt: str) -> Dict[str, Any]:
        """Geração de texto simples para chat direto."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=payload, timeout=30.0)
                data = response.json()
                return {"reply_text": data["choices"][0]["message"]["content"]}
            except Exception as e:
                logger.error(f"Erro em Groq generate_response: {e}")
                return {"reply_text": "Erro ao gerar resposta."}
