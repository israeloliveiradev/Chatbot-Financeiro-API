from typing import List, Dict
import logging
from src.adapters.llm.base import LLMClient

logger = logging.getLogger(__name__)

class SummarizeHistory:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

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
            response = await self.llm_client.generate_response(prompt)
            return response.get("reply_text", "").strip()
        except Exception as e:
            logger.error(f"Erro ao sumarizar histórico: {e}")
            return "Histórico longo (erro na sumarização)."
