from typing import List, Dict
import logging
from src.adapters.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class SummarizeHistory:
    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client

    async def execute(self, history: List[Dict[str, str]]) -> str:
        """
        Gera um resumo conciso do histórico de conversas fornecido.
        """
        if not history:
            return ""

        text_to_summarize = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        
        prompt = f"""
        Resuma a seguinte conversa de um assistente financeiro com um cliente de forma extremamente concisa (máximo 3 frases).
        Foque nos fatos financeiros discutidos e decisões tomadas.
        
        CONVERSA:
        {text_to_summarize}
        
        RESUMO:
        """
        
        try:
            # Usando o chat sem tools para um resumo simples
            # Criamos um modelo temporário no GeminiClient para isso se necessário, 
            # ou apenas usamos o chat() passando uma instrução que ignore tools.
            # Por simplicidade, assumimos que chat() funciona bem para isso se não houver tool call induzida.
            response = await self.gemini_client.chat(
                system_instruction="Você é um sintetizador de conversas financeiras.",
                history=[],
                message=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Erro ao sumarizar histórico: {e}")
            return "Histórico longo (erro na sumarização)."
