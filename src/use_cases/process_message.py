from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional
import logging

from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.contribution_repository import ContributionRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.adapters.cache.redis_session import RedisSession
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.llm.gemini_client import GeminiClient

from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.use_cases.get_goals import GetGoals
from src.use_cases.create_goal import CreateGoal
from src.use_cases.register_contribution import RegisterContribution
from src.use_cases.cancel_goal import CancelGoal
from src.use_cases.simulate_purchase import SimulatePurchase

logger = logging.getLogger(__name__)

class ProcessMessage:
    def __init__(
        self,
        client_repo: ClientRepository,
        spending_repo: SpendingRepository,
        goal_repo: GoalRepository,
        contribution_repo: ContributionRepository,
        uow: UnitOfWork,
        redis_session: RedisSession,
        evolution_client: EvolutionClient,
        gemini_client: GeminiClient,
    ):
        self.client_repo = client_repo
        self.spending_repo = spending_repo
        self.goal_repo = goal_repo
        self.contribution_repo = contribution_repo
        self.uow = uow
        self.redis_session = redis_session
        self.evolution_client = evolution_client
        self.gemini_client = gemini_client

    async def execute(self, phone: str, text: str):
        logger.info(f"Processando mensagem de {phone}: {text[:50]}...")
        
        async with self.uow:
            # 1. Buscar cliente
            client = await GetClientByPhone(self.client_repo).execute(phone)
            if not client:
                await self.evolution_client.send_text_message(
                    phone, 
                    "Olá! Não encontrei seu cadastro. Por favor, entre em contato com o suporte para ativar seu assistente financeiro."
                )
                return

            # 2. Carregar sessão
            session = await self.redis_session.get_session(phone)
            
            # 3. Lidar com confirmações pendentes
            if session.get("pending_action"):
                await self._handle_pending_action(phone, text, session, client)
                return

            # 4. Preparar contexto para o LLM
            current_date = date.today()
            spendings_summary = await GetMonthlySpending(self.spending_repo).execute(client.id, current_date)
            goals = await GetGoals(self.goal_repo).execute(client.id)
            
            system_prompt = self.gemini_client.prompt_builder.build_system_prompt(
                client=client,
                monthly_goals=[],
                goals=goals,
                spendings_summary=spendings_summary
            )

            # 5. Analisar com Gemini
            try:
                llm_result = await self.gemini_client.analyze_message(
                    system_prompt=system_prompt,
                    history=session["history"],
                    current_message=text
                )
            except Exception as e:
                logger.error(f"Erro ao chamar Gemini: {e}")
                await self.evolution_client.send_text_message(phone, "Desculpe, tive um probleminha técnico agora. Pode repetir em instantes?")
                return

            intent = llm_result.get("intent")
            data = llm_result.get("extracted_data", {})
            response_text = llm_result.get("response", "Entendido. Como posso ajudar mais?")

            # 6. Orquestrar Intenções
            await self._orchestrate_intent(intent, data, client, phone, response_text, current_date)

            # 7. Atualizar Histórico
            await self.redis_session.add_history(phone, "user", text)
            await self.redis_session.add_history(phone, "assistant", response_text)

    async def _handle_pending_action(self, phone: str, text: str, session: Dict, client: Any):
        lower_txt = text.lower().strip()
        confirm_words = ["sim", "s", "confirmo", "pode", "isso", "ok", "com certeza"]
        
        action = session["pending_action"]
        data = session["pending_data"]

        if any(word in lower_txt for word in confirm_words):
            try:
                if action == "confirm_create_goal":
                    await CreateGoal(self.goal_repo).execute(
                        client.id,
                        data["title"],
                        Decimal(str(data["target_amount"])),
                        date.fromisoformat(data["deadline"]) if data.get("deadline") else None
                    )
                    await self.evolution_client.send_text_message(phone, "✅ Meta criada com sucesso!")
                
                elif action == "confirm_cancel_goal":
                    await CancelGoal(self.goal_repo).execute(data["goal_id"])
                    await self.evolution_client.send_text_message(phone, "🗑️ Meta cancelada.")
            except Exception as e:
                logger.error(f"Erro ao processar ação pendente {action}: {e}")
                await self.evolution_client.send_text_message(phone, "Houve um erro ao processar sua confirmação.")
        else:
            await self.evolution_client.send_text_message(phone, "Entendido. Ação cancelada.")
        
        await self.redis_session.clear_pending_action(phone)

    async def _orchestrate_intent(self, intent: str, data: Dict, client: Any, phone: str, response_text: str, current_date: date):
        if intent == "criar_objetivo":
            if data.get("title") and data.get("target_amount"):
                await self.redis_session.set_pending_action(phone, "confirm_create_goal", data)
        
        elif intent == "simular_compra":
            cat = data.get("category")
            amount = data.get("purchase_amount")
            if cat and amount:
                sim = await SimulatePurchase(self.spending_repo).execute(client.id, cat, Decimal(str(amount)), current_date)
                if not sim["can_buy"]:
                    # Sobrescrevemos ou anexamos o alerta se o LLM não percebeu (redundância senior)
                    response_text += f"\n\n🚨 *ALERTA:* Notei que isso ultrapassa seu limite em {cat}."
        
        # Envia a mensagem final (seja ela qual for)
        await self.evolution_client.send_text_message(phone, response_text)
