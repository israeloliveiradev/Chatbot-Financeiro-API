import json
from typing import Dict, Any, List, Optional
import redis.asyncio as redis

from src.infra.config import settings

class RedisSession:
    def __init__(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl = 1800  # 30 minutos em segundos

    def _get_key(self, phone: str) -> str:
        return f"session:{phone}"

    async def get_session(self, phone: str) -> Dict[str, Any]:
        """
        Retorna o estado da sessão atual do usuário pelo telefone.
        Se não existir, retorna um novo estado vazio.
        """
        key = self._get_key(phone)
        data = await self.redis.get(key)
        
        if data:
            return json.loads(data)
            
        return {
            "pending_action": None,
            "pending_data": {},
            "history": []
        }

    async def save_session(self, phone: str, session_data: Dict[str, Any]) -> None:
        """
        Salva o estado da sessão no Redis com TTL de 30 minutos.
        """
        key = self._get_key(phone)
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(session_data)
        )

    async def clear_session(self, phone: str) -> None:
        """
        Limpa a sessão explicitamente (útil após concluir um fluxo).
        """
        key = self._get_key(phone)
        await self.redis.delete(key)

    async def add_history(self, phone: str, role: str, content: str) -> None:
        """
        Método auxiliar para adicionar uma mensagem ao histórico e renovar o TTL.
        """
        session = await self.get_session(phone)
        
        session["history"].append({
            "role": role,
            "content": content
        })
        
        # Manter apenas as últimas 20 mensagens para não estourar contexto
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]
            
        await self.save_session(phone, session)

    async def set_pending_action(self, phone: str, action: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Define uma ação pendente (ex: aguardando confirmação Sim/Não).
        """
        session = await self.get_session(phone)
        session["pending_action"] = action
        session["pending_data"] = data or {}
        await self.save_session(phone, session)

    async def clear_pending_action(self, phone: str) -> None:
        """
        Limpa a ação pendente preservando o histórico.
        """
        session = await self.get_session(phone)
        session["pending_action"] = None
        session["pending_data"] = {}
        await self.save_session(phone, session)

    async def get_api_usage(self, phone: str) -> int:
        """
        Retorna a contagem de mensagens do usuário nas últimas 24h.
        """
        key = f"usage:{phone}"
        count = await self.redis.get(key)
        return int(count) if count else 0

    async def increment_api_usage(self, phone: str) -> int:
        """
        Incrementa a contagem de mensagens e define TTL de 24h se for novo.
        """
        key = f"usage:{phone}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 86400) # 24 horas
        return count
