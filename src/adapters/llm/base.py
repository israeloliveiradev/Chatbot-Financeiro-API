from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LLMClient(ABC):
    @abstractmethod
    async def analyze_message(self, system_prompt: str, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Analisa a mensagem do usuário e retorna um JSON com intent e extração.
        O prompt de sistema contém o contexto e instruções, e a user_message é a entrada bruta.
        """
        ...

    @abstractmethod
    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str) -> str:
        """
        Transcreve áudio para texto.
        """
        ...

    @abstractmethod
    async def generate_response(self, prompt: str) -> Dict[str, Any]:
        """
        Gera uma resposta de texto livre.
        """
        ...
