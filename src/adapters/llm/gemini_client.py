import json
import logging
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types
import os

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
    "responder_conversa": "conversa",
}


class GeminiClient:
    def __init__(self, prompt_builder=None, tools=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY não configurada")
            raise ValueError("GEMINI_API_KEY não configurada")

        self.client = genai.Client(api_key=api_key)
        self.prompt_builder = prompt_builder
        self.model_name = "gemini-2.5-flash-lite"

        if tools:
            self.tools = [
                types.Tool(function_declarations=[
                    types.FunctionDeclaration.from_callable(client=self.client, callable=fn)
                    for fn in tools
                ])
            ]
        else:
            self.tools = None

        self.safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE",
            ),
        ]

    def _function_call_to_json(self, function_call) -> str:
        """
        Converte um function_call do Gemini para o JSON
        esperado pelo process_message.
        """
        name = function_call.name
        args = dict(function_call.args) if function_call.args else {}
        intent = _TOOL_TO_INTENT.get(name, "conversa")

        # Se for responder_conversa, o reply_text vem dos argumentos
        reply_text = args.get("reply_text", "") if intent == "conversa" else ""

        logger.info(f"[GEMINI] Function call: {name}({args}) -> intent: {intent}")

        result = {
            "intent": intent,
            "extracted_data": args,
            "reply_text": reply_text,
        }

        return json.dumps(result, ensure_ascii=False)

    async def analyze_message(self, prompt: str, history: List[Dict[str, str]] = None) -> str:
        """
        Analisa a mensagem do usuário usando o Gemini.
        Retorna SEMPRE uma string JSON válida para o process_message.
        """
        try:
            config = types.GenerateContentConfig(
                safety_settings=self.safety_settings,
                tools=self.tools,
            )

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            # Log para debug (útil se o JSON falhar)
            logger.debug(f"[GEMINI] Raw Response: {response}")

            # 1) Verificar se veio function_call
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        return self._function_call_to_json(part.function_call)

            # 2) Se veio texto livre (não-tool), envelopamos como 'conversa'
            if response.text:
                text = response.text.strip()
                # Se o Gemini ignorar as tools e retornar JSON por conta própria, tentamos validar
                if text.startswith("{") and text.endswith("}"):
                    try:
                        json.loads(text)
                        return text # Já é um JSON
                    except:
                        pass
                
                # Caso contrário, envelopamos
                return json.dumps({
                    "intent": "conversa",
                    "extracted_data": {},
                    "reply_text": text
                }, ensure_ascii=False)

            # 3) Fallback absoluto para evitar erro no process_message
            return json.dumps({
                "intent": "conversa",
                "extracted_data": {},
                "reply_text": "Desculpe, me perdi um pouco. Pode repetir? 😅"
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Erro ao chamar Gemini: {e}")
            raise

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Transcreve um áudio usando as capacidades multimodais do Gemini.
        """
        try:
            contents = [
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcreva exatamente o que foi dito neste áudio. Retorne apenas o texto transcrito, sem comentários adicionais.",
            ]

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"Erro na transcrição de áudio: {e}")
            return ""

    async def generate_response(self, prompt: str) -> Dict[str, Any]:
        """
        Gera uma resposta de texto livre (para insights do relatório, etc).
        Retorna no formato {'reply_text': '...'} para consistência.
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(safety_settings=self.safety_settings)
            )
            return {"reply_text": response.text or ""}
        except Exception as e:
            logger.error(f"Erro em generate_response: {e}")
            return {"reply_text": ""}
