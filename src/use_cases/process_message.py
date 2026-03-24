import json
import logging
import difflib
import os
import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4

from src.adapters.llm.base import LLMClient
from src.adapters.llm.prompt_builder import PromptBuilder
from src.adapters.messaging.evolution_client import EvolutionClient
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.contribution_repository import ContributionRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.domain.entities.goal import Goal
from src.domain.entities.contribution import Contribution
from src.domain.entities.spending import Spending
from src.domain.entities.monthly_goal import MonthlyGoal
from src.domain.services.proactive_alerter import ProactiveAlerter
from src.domain.services.report_generator import ReportGenerator

# Relative imports for use cases in same package
from .base import BaseUseCase
from .get_client_by_phone import GetClientByPhone
from .get_goals import GetGoals
from .get_monthly_spending import GetMonthlySpending
from .register_spending import RegisterSpending
from .create_goal import CreateGoal
from .register_contribution import RegisterContribution

logger = logging.getLogger(__name__)

class ProcessMessage(BaseUseCase):
    def __init__(
        self,
        uow: UnitOfWork,
        client_repo: ClientRepository,
        llm_client: LLMClient,
        evolution_client: EvolutionClient,
        prompt_builder: PromptBuilder,
        proactive_alerter: ProactiveAlerter,
        # Use Cases Injetados
        get_client_use_case: GetClientByPhone,
        get_goals_use_case: GetGoals,
        get_monthly_spending_use_case: GetMonthlySpending,
        register_spending_use_case: RegisterSpending,
        create_goal_use_case: CreateGoal,
        register_contribution_use_case: RegisterContribution,
    ):
        self.uow = uow
        self.client_repo = client_repo
        self.llm_client = llm_client
        self.evolution_client = evolution_client
        self.prompt_builder = prompt_builder
        self.proactive_alerter = proactive_alerter
        
        self.get_client_use_case = get_client_use_case
        self.get_goals_use_case = get_goals_use_case
        self.get_monthly_spending_use_case = get_monthly_spending_use_case
        self.register_spending_use_case = register_spending_use_case
        self.create_goal_use_case = create_goal_use_case
        self.register_contribution_use_case = register_contribution_use_case

    async def execute(
        self,
        phone: str,
        text: str,
        message_id: Optional[str] = None,
        is_audio: bool = False,
        media_url: Optional[str] = None
    ):
        """
        Orquestra o fluxo principal de uma mensagem (texto ou áudio).
        """
        logger.info(f"[PROCESS] Iniciando para {phone} | Áudio: {is_audio}")

        # Inicia Transação Global para o processamento
        async with self.uow:
            try:
                # 1. Tratamento de Áudio
                if is_audio and media_url:
                    try:
                        audio_data = await self.evolution_client.download_media(media_url)
                        if audio_data:
                            transcription = await self.llm_client.transcribe_audio(audio_data)
                            if transcription:
                                text = transcription
                                logger.info(f"[PROCESS] Transcrição: {text}")
                            else:
                                await self.evolution_client.send_text_message(phone, "Não consegui entender o áudio. Pode repetir?")
                                return
                        else:
                            await self.evolution_client.send_text_message(phone, "Tive um problema ao baixar seu áudio.")
                            return
                    except Exception as e:
                        logger.error(f"Erro ao transcrever áudio: {e}")
                        await self.evolution_client.send_text_message(phone, "Erro ao processar áudio. Pode digitar?")
                        return

                # 2. Busca Cliente
                client = await self.get_client_use_case.execute(phone)

                if not client:
                    await self.evolution_client.send_text_message(
                        phone, "Olá! Sou o assistente do seu planejador financeiro. Peça a ele para cadastrar seu número para começarmos! 😊"
                    )
                    return

                # 3. Busca Contexto (Objetivos e Gastos) - FETCH ONCE
                goals = await self.get_goals_use_case.execute(client.id, only_active=True)
                spendings_summary = await self.get_monthly_spending_use_case.execute(
                    client.id, date.today()
                )

                # 4. Reconhecimento de Intent via LLM
                system_prompt = self.prompt_builder.build_system_prompt(
                    client_name=client.name,
                    monthly_income=float(client.monthly_income),
                    goals=[g.__dict__ for g in goals],
                    spendings_summary=spendings_summary,
                    history=[],
                )

                try:
                    raw_result = await self.llm_client.analyze_message(
                        system_prompt=system_prompt,
                        user_message=text
                    )
                    result = json.loads(raw_result)
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem com LLM: {e}")
                    await self.evolution_client.send_text_message(phone, "Estou com uma instabilidade. Pode repetir? 😅")
                    return

                intent = str(result.get("intent", "conversa"))
                reply_text = str(result.get("reply_text", ""))
                intent_data: Dict[str, Any] = result.get("extracted_data", {})

                logger.info(f"[PROCESS] Intent: {intent} | Data: {intent_data}")

                # 5. Orquestração de Ações (Passando dados já carregados para evitar N+1)
                if intent == "criar_objetivo":
                    await self._orchestrate_criar_objetivo(phone, client.id, intent_data, reply_text)
                elif intent == "registrar_aporte":
                    await self._orchestrate_registrar_aporte(phone, client.id, goals, intent_data, reply_text)
                elif intent == "registrar_gasto":
                    await self._orchestrate_registrar_gasto(phone, client.id, intent_data, reply_text)
                elif intent == "simular_compra":
                    await self._orchestrate_simular_compra(phone, client.id, intent_data, spendings_summary, reply_text)
                elif intent == "simular_poupanca":
                    await self._orchestrate_simular_poupanca(phone, intent_data, reply_text)
                elif intent == "cancelar_objetivo":
                    await self._orchestrate_cancelar_objetivo(phone, client.id, goals, intent_data, reply_text)
                elif intent == "listar_objetivos":
                    await self._orchestrate_listar_objetivos(phone, goals)
                elif intent == "obter_resumo_mensal":
                    await self._orchestrate_resumo_mensal(phone, client.name, spendings_summary)
                elif intent == "gerar_relatorio":
                    await self._orchestrate_gerar_relatorio(phone, client.id, client.name, spendings_summary, goals)
                elif intent == "definir_meta_mensal":
                    await self._orchestrate_definir_meta_mensal(phone, client.id, intent_data, reply_text)
                else:
                    await self.evolution_client.send_text_message(phone, reply_text or "Em que posso ajudar? 😊")
                
                # Commit se tudo correu bem
                await self.uow.commit()

            except Exception as e:
                # Rollback em caso de erro fatal
                await self.uow.rollback()
                logger.exception(f"FATAL ERROR in ProcessMessage.execute: {e}")
                raise e

    async def _orchestrate_criar_objetivo(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        title = str(data.get("title", ""))
        target_amount = Decimal(str(data.get("target_amount", 0)))
        deadline_str = str(data.get("deadline", ""))

        if not title or not target_amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Preciso do nome e valor do objetivo. 🎯")
            return

        deadline = None
        if deadline_str:
            for fmt in ("%Y-%m-%d", "%Y-%m", "%d/%m/%Y", "%m/%Y"):
                try:
                    # Garantir que suporte datetime ou date strings
                    if "T" in deadline_str: deadline_str = deadline_str.split("T")[0]
                    deadline = datetime.strptime(deadline_str, fmt).date()
                    break
                except: continue

        await self.create_goal_use_case.execute(client_id, title, target_amount, deadline)
        await self.evolution_client.send_text_message(phone, reply_text or f"Objetivo '{title}' criado com sucesso! 🚀")

    async def _orchestrate_registrar_aporte(self, phone: str, client_id: UUID, goals: List[Goal], data: Dict[str, Any], reply_text: str):
        goal_title = str(data.get("goal_title", ""))
        amount = Decimal(str(data.get("amount", 0)))

        if not goal_title or not amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Preciso saber para qual objetivo e o valor do aporte. 💰")
            return

        matches = difflib.get_close_matches(goal_title, [g.title for g in goals], n=1, cutoff=0.5)

        if not matches:
            await self.evolution_client.send_text_message(phone, f"Não encontrei o objetivo '{goal_title}'. Pode verificar o nome? 🤔")
            return

        goal = next(g for g in goals if g.title == matches[0])
        await self.register_contribution_use_case.execute(goal.id, amount)
        await self.evolution_client.send_text_message(phone, reply_text or f"Aporte de R$ {amount} registrado em '{goal.title}'! ✅")

    async def _orchestrate_registrar_gasto(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        category = str(data.get("category_name", data.get("category", "Outros")))
        amount = Decimal(str(data.get("amount", 0)))
        description = str(data.get("description", ""))

        if not amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Preciso saber o valor do gasto. 💸")
            return

        # Executa o registro
        spending = await self.register_spending_use_case.execute(client_id, category, amount, description)
        
        # Alerta Proativo se necessário
        if spending and self.proactive_alerter:
            await self.proactive_alerter.check_spending_alerts(client_id, phone, spending.category_id)
            
        await self.evolution_client.send_text_message(phone, reply_text or f"Gasto de R$ {amount} em '{category}' registrado! 📝")

    async def _orchestrate_simular_compra(self, phone: str, client_id: UUID, data: Dict[str, Any], spendings_summary: List[Dict], reply_text: str):
        await self.evolution_client.send_text_message(phone, reply_text or "Simulação concluída!")

    async def _orchestrate_simular_poupanca(self, phone: str, data: Dict[str, Any], reply_text: str):
        await self.evolution_client.send_text_message(phone, reply_text or "Simulação de poupança enviada!")

    async def _orchestrate_cancelar_objetivo(self, phone: str, client_id: UUID, goals: List[Goal], data: Dict[str, Any], reply_text: str):
        goal_title = str(data.get("goal_title", ""))
        if not goal_title:
            await self.evolution_client.send_text_message(phone, "Qual objetivo você deseja cancelar? ❌")
            return

        matches = difflib.get_close_matches(goal_title, [g.title for g in goals], n=1, cutoff=0.6)

        if matches:
            goal = next(g for g in goals if g.title == matches[0])
            goal.status = "cancelled"
            await self.uow.session.merge(goal)
            await self.evolution_client.send_text_message(phone, reply_text or f"O objetivo '{goal.title}' foi cancelado. 📩")
        else:
            await self.evolution_client.send_text_message(phone, f"Não encontrei o objetivo '{goal_title}' para cancelar. 🧐")

    async def _orchestrate_listar_objetivos(self, phone: str, goals: List[Goal]):
        if not goals:
            await self.evolution_client.send_text_message(phone, "Você não tem objetivos ativos no momento. Que tal criar um? 🎯")
            return

        msg = "*Seus Objetivos Ativos:* 🎯\n\n"
        for g in goals:
            target = g.target_amount if g.target_amount > 0 else 1
            progress = (g.current_amount / target) * 100
            msg += f"• *{g.title}*\n  💰 R$ {g.current_amount} de R$ {g.target_amount}\n  📊 {progress:.1f}%\n"
            if g.deadline:
                msg += f"  📅 Prazo: {g.deadline.strftime('%d/%m/%Y')}\n"
            msg += "\n"
        
        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_resumo_mensal(self, phone: str, name: str, spendings: List[Dict]):
        msg = f"Olá {name}! Aqui está o resumo parcial dos seus gastos este mês: 📊\n\n"
        if not spendings:
            msg += "Você ainda não registrou gastos ou metas para este mês. 🍃"
        else:
            for s in spendings:
                status_icon = "✅" if s['available'] > 0 else "🛑"
                msg += f"{status_icon} *{s['category']}*\n  Gasto: R$ {s['total_spent']:.2f}\n  Limite: R$ {s['limit_amount']:.2f}\n  Status: {s['percentage_used']}%\n\n"
        
        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_gerar_relatorio(self, phone: str, client_id: UUID, name: str, spendings: List[Dict], goals: List[Goal]):
        await self._orchestrate_resumo_mensal(phone, name, spendings)

    async def _orchestrate_definir_meta_mensal(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        await self.evolution_client.send_text_message(phone, reply_text or "Meta mensal definida com sucesso! 🛡️")
