import json
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Any, Optional
import difflib

from src.adapters.llm.gemini_client import GeminiClient
from src.adapters.llm.prompt_builder import PromptBuilder
from src.adapters.messaging.evolution_client import EvolutionClient
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.entities.goal import Goal
from src.domain.entities.contribution import Contribution
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_goals import GetGoals
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.use_cases.register_contribution import RegisterContribution
from src.use_cases.simulate_savings import SimulateSavings

logger = logging.getLogger(__name__)

class ProcessMessage:
    def __init__(
        self,
        uow: UnitOfWork,
        client_repo: ClientRepository,
        goal_repo: GoalRepository,
        spending_repo: SpendingRepository,
        gemini_client: GeminiClient,
        evolution_client: EvolutionClient,
        prompt_builder: PromptBuilder,
    ):
        self.uow = uow
        self.client_repo = client_repo
        self.goal_repo = goal_repo
        self.spending_repo = spending_repo
        self.gemini_client = gemini_client
        self.evolution_client = evolution_client
        self.prompt_builder = prompt_builder

    async def execute(self, phone: str, text: str, audio_bytes: bytes = None, audio_mimetype: str = None) -> None:
        """
        Orquestra o processamento de uma mensagem (texto ou áudio).
        """
        # 1. Transcrição se for áudio
        if not text and audio_bytes:
            text = await self.gemini_client.transcribe_audio(audio_bytes, audio_mimetype)
            if not text:
                await self.evolution_client.send_text_message(phone, "Não consegui entender o áudio. Pode repetir por texto? 🧐")
                return

        # 2. Busca contexto do cliente
        client = await GetClientByPhone(self.client_repo).execute(phone)
        if not client:
            await self.evolution_client.send_text_message(phone, "Olá! Sou seu assistente financeiro. Para começar, precisamos cadastrar você no sistema via painel administrativo. 😉")
            return

        # 3. Busca objetivos e resumos (para o prompt)
        goals = await GetGoals(self.goal_repo).execute(client.id, only_active=True)
        spendings_summary = await GetMonthlySpending(self.spending_repo).execute(client.id, date.today())
        
        # Histórico (simulando para o prompt)
        history = [] # TODO: Buscar histórico real do banco se necessário

        # 4. Reconhecimento de Intent via Gemini
        prompt = self.prompt_builder.build_system_prompt(
            client_name=client.name,
            monthly_income=float(client.monthly_income),
            goals=[g.__dict__ for g in goals],
            spendings_summary=spendings_summary,
            history=history
        )
        
        full_prompt = f"{prompt}\n\nMENSAGEM DO USUÁRIO: {text}"
        
        try:
            raw_response = await self.gemini_client.analyze_message(full_prompt)
            # Limpa possíveis backticks de markdown do Gemini
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            response_data = json.loads(clean_json)
        except Exception as e:
            logger.error(f"Erro ao processar resposta do Gemini: {e}")
            await self.evolution_client.send_text_message(phone, "Ops, me enrolei aqui. Pode falar de novo? 😅")
            return

        intent = response_data.get("intent", "conversa")
        reply_text = response_data.get("reply_text", "Em que posso ajudar?")
        extracted_data = response_data.get("extracted_data", {})

        # 5. Orquestração de Ações
        if intent == "registrar_aporte":
            await self._orchestrate_registrar_aporte(phone, client.id, extracted_data, reply_text)
        elif intent == "simular_poupanca":
            await self._orchestrate_simular_poupanca(phone, extracted_data, reply_text)
        elif intent == "cancelar_objetivo":
            await self._orchestrate_cancelar_objetivo(phone, client.id, extracted_data, reply_text)
        else:
            # Intents de simples conversa ou criação de objetivo (que o bot orienta por texto)
            await self.evolution_client.send_text_message(phone, reply_text)

    async def _orchestrate_registrar_aporte(self, phone: str, client_id: Any, data: Dict[str, Any], reply_text: str):
        goal_title = data.get("goal_title")
        amount = data.get("amount")
        
        if not goal_title or not amount:
            await self.evolution_client.send_text_message(phone, reply_text)
            return

        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)
        if not goals:
            await self.evolution_client.send_text_message(phone, "Você não tem nenhum objetivo ativo para guardar dinheiro. Quer criar um? 🎯")
            return

        # Fuzzy matching para encontrar o objetivo pelo título
        goal_names = [g.title for g in goals]
        matches = difflib.get_close_matches(goal_title, goal_names, n=1, cutoff=0.4)
        
        if not matches:
            await self.evolution_client.send_text_message(phone, f"Não encontrei nenhum objetivo parecido com '{goal_title}'. Pode confirmar o nome? 🧐")
            return
            
        target_goal = next(g for g in goals if g.title == matches[0])
        
        # Executa o aporte
        uc = RegisterContribution(self.uow, self.goal_repo)
        await uc.execute(target_goal.id, Decimal(str(amount)))
        
        success_msg = f"✅ Boas notícias! Registrei o aporte de R$ {amount:.2f} no objetivo '{target_goal.title}'. Rumo à meta! 🚀\n\n{reply_text}"
        await self.evolution_client.send_text_message(phone, success_msg)

    async def _orchestrate_simular_poupanca(self, phone: str, data: Dict[str, Any], reply_text: str):
        target_amount = data.get("target_amount")
        monthly_saving = data.get("monthly_saving")
        
        if not target_amount or not monthly_saving:
            await self.evolution_client.send_text_message(phone, reply_text)
            return
            
        uc = SimulateSavings()
        result = await uc.execute(Decimal(str(target_amount)), Decimal(str(monthly_saving)), date.today())
        
        if result["possible"]:
            msg = (
                f"📊 *Simulação de Poupança*\n\n"
                f"Para juntar R$ {target_amount:.2f} guardando R$ {monthly_saving:.2f} por mês:\n"
                f"⏱️ Tempo: {result['months_needed']} meses\n"
                f"📅 Data prevista: {datetime.fromisoformat(result['estimated_date']).strftime('%m/%Y')}\n\n"
                f"{reply_text}"
            )
        else:
            msg = f"❌ Não consegui simular: {result.get('reason')}\n\n{reply_text}"
            
        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_cancelar_objetivo(self, phone: str, client_id: Any, data: Dict[str, Any], reply_text: str):
        # Para cancelamento, o bot apenas confirma via texto por enquanto, 
        # ou podemos implementar a deleção real se o cliente confirmar.
        # Aqui vamos apenas buscar se existe o objetivo para dar uma resposta melhor.
        goal_title = data.get("goal_title")
        if not goal_title:
             await self.evolution_client.send_text_message(phone, reply_text)
             return
             
        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)
        goal_names = [g.title for g in goals]
        matches = difflib.get_close_matches(goal_title, goal_names, n=1, cutoff=0.5)
        
        if matches:
            await self.evolution_client.send_text_message(phone, f"Entendido. Você quer cancelar '{matches[0]}'. Para confirmar, use o nosso painel administrativo ou peça explicitamente aqui. (Funcionalidade em implementação 🚧)\n\n{reply_text}")
        else:
            await self.evolution_client.send_text_message(phone, reply_text)
from datetime import datetime
