import json
import logging
import difflib
import os
import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4

from src.adapters.llm.gemini_client import GeminiClient
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
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_goals import GetGoals
from src.use_cases.get_monthly_spending import GetMonthlySpending

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
        contribution_repo: ContributionRepository,
    ):
        self.uow = uow
        self.client_repo = client_repo
        self.goal_repo = goal_repo
        self.spending_repo = spending_repo
        self.contribution_repo = contribution_repo
        self.gemini_client = gemini_client
        self.evolution_client = evolution_client
        self.prompt_builder = prompt_builder
        self.alerter = ProactiveAlerter(spending_repo, evolution_client)
        self.report_generator = ReportGenerator()

    async def _send_with_typing(self, phone: str, text: str, delay_ms: int = 2000):
        """Simula digitação e envia mensagem de texto."""
        await self.evolution_client.send_presence(phone, "composing", delay_ms)
        await asyncio.sleep(delay_ms / 1000)
        await self.evolution_client.send_text_message(phone, text)

    async def _send_buttons_with_typing(self, phone: str, title: str, description: str, buttons: list, delay_ms: int = 1500):
        """Simula digitação e envia botões interativos."""
        await self.evolution_client.send_presence(phone, "composing", delay_ms)
        await asyncio.sleep(delay_ms / 1000)
        await self.evolution_client.send_buttons(phone, title, description, buttons)

    async def execute(
        self,
        phone: str,
        text: str,
        message_id: Optional[str] = None,
        is_audio: bool = False,
        media_url: Optional[str] = None,
    ) -> None:
        """
        Orquestra o processamento de uma mensagem (texto ou áudio).
        """
        # 1. Transcrição se for áudio (Feature 7)
        if is_audio and media_url:
            await self.evolution_client.send_text_message(phone, "🎧 _Ouvindo seu áudio com atenção..._")
            try:
                audio_bytes = await self.evolution_client.download_media(media_url)
                if audio_bytes:
                    transcription = await self.gemini_client.transcribe_audio(audio_bytes, "audio/mp4")
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
        get_client_use_case = GetClientByPhone(self.client_repo)
        client = await get_client_use_case.execute(phone)

        if not client:
            await self.evolution_client.send_text_message(
                phone, "Olá! Sou o assistente do seu planejador financeiro. Peça a ele para cadastrar seu número para começarmos! 😊"
            )
            return

        # 3. Busca Contexto (Objetivos e Gastos)
        goals = await GetGoals(self.goal_repo).execute(client.id, only_active=True)
        spendings_summary = await GetMonthlySpending(self.spending_repo).execute(
            client.id, date.today()
        )

        # 4. Reconhecimento de Intent via Gemini
        system_prompt = self.prompt_builder.build_system_prompt(
            client_name=client.name,
            monthly_income=float(client.monthly_income),
            goals=[g.__dict__ for g in goals],
            spendings_summary=spendings_summary,
            history=[],
        )

        full_prompt = f"{system_prompt}\n\nMENSAGEM DO USUÁRIO: {text}"

        try:
            # Correção: O gemini_client.analyze_message retorna JSON string
            raw_result = await self.gemini_client.analyze_message(full_prompt)
            result = json.loads(raw_result)
        except Exception as e:
            logger.error(f"Erro ao processar com Gemini: {e}")
            await self.evolution_client.send_text_message(phone, "Estou com uma instabilidade. Pode repetir? 😅")
            return

        intent = str(result.get("intent", "conversa"))
        reply_text = str(result.get("reply_text", ""))
        intent_data: Dict[str, Any] = result.get("extracted_data", {})

        logger.info(f"[PROCESS] Intent: {intent} | Data: {intent_data}")

        # 5. Orquestração de Ações
        if intent == "criar_objetivo":
            await self._orchestrate_criar_objetivo(phone, client.id, intent_data, reply_text)
        elif intent == "registrar_aporte":
            await self._orchestrate_registrar_aporte(phone, client.id, intent_data, reply_text)
        elif intent == "registrar_gasto":
            await self._orchestrate_registrar_gasto(phone, client.id, intent_data, reply_text)
        elif intent == "simular_compra":
            await self._orchestrate_simular_compra(phone, client.id, intent_data, spendings_summary, reply_text)
        elif intent == "simular_poupanca":
            await self._orchestrate_simular_poupanca(phone, intent_data, reply_text)
        elif intent == "cancelar_objetivo":
            await self._orchestrate_cancelar_objetivo(phone, client.id, intent_data, reply_text)
        elif intent == "listar_objetivos":
            await self._orchestrate_listar_objetivos(phone, client.id)
        elif intent == "obter_resumo_mensal":
            await self._orchestrate_resumo_mensal(phone, client.id, client.name, spendings_summary)
        elif intent == "gerar_relatorio":
            await self._orchestrate_gerar_relatorio(phone, client.id, client.name, spendings_summary, goals)
        elif intent == "definir_meta_mensal":
            await self._orchestrate_definir_meta_mensal(phone, client.id, intent_data, reply_text)
        else:
            await self.evolution_client.send_text_message(phone, reply_text or "Em que posso ajudar? 😊")

    async def _orchestrate_criar_objetivo(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        title = str(data.get("title", ""))
        target_amount = float(data.get("target_amount", 0))
        deadline_str = str(data.get("deadline", ""))

        if not title or not target_amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Preciso do nome e valor do objetivo. 🎯")
            return

        deadline = None
        if deadline_str:
            for fmt in ("%Y-%m-%d", "%Y-%m", "%d/%m/%Y", "%m/%Y"):
                try:
                    deadline = datetime.strptime(deadline_str, fmt).date()
                    break
                except ValueError: continue

        goal = Goal(
            id=uuid4(),
            client_id=client_id,
            title=title,
            target_amount=Decimal(str(target_amount)),
            current_amount=Decimal("0"),
            deadline=deadline,
            status="active",
        )
        await self.goal_repo.create(goal)

        msg = (
            f"✅ *Objetivo criado com sucesso!*\n\n"
            f"🎯 *{title}*\n"
            f"💰 Meta: *R$ {target_amount:,.2f}*\n"
            f"📅 Prazo: {deadline.strftime('%d/%m/%Y') if deadline else 'Sem prazo'}\n"
        )
        if reply_text: msg += f"\n{reply_text}"
        
        # NUDGE (Feature 2)
        buttons = [{"id": "APT_S", "label": "Sim, comece com 10%"}, {"id": "APT_N", "label": "Talvez depois"}]
        await self._send_buttons_with_typing(phone, "Objetivo Salvo", f"{msg}\nDeseja realizar seu primeiro aporte agora?", buttons, 1500)

    async def _orchestrate_registrar_aporte(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        goal_title = str(data.get("goal_title", ""))
        amount = float(data.get("amount", 0))

        if not goal_title or not amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Qual o valor e o objetivo?")
            return

        # Correção: Usar Use Case GetGoals
        get_goals_use_case = GetGoals(self.goal_repo)
        goals = await get_goals_use_case.execute(client_id, only_active=True)
        
        goal = next((g for g in goals if g.title.lower() == goal_title.lower()), None)

        if not goal:
            titles = [g.title for g in goals]
            closest = difflib.get_close_matches(goal_title, titles, n=1, cutoff=0.6)
            if closest:
                goal = next(g for g in goals if g.title == closest[0])
            else:
                await self.evolution_client.send_text_message(phone, f"Objetivo '{goal_title}' não encontrado.")
                return

        contribution = Contribution(
            id=uuid4(), goal_id=goal.id, client_id=client_id,
            amount=Decimal(str(amount)), contributed_at=datetime.now()
        )
        await self.contribution_repo.create(contribution)
        
        goal.current_amount += Decimal(str(amount))
        await self.goal_repo.update(goal)

        msg = f"🚀 *Aporte registrado!*\n\n🎯 {goal.title}\n💰 R$ {amount:,.2f}\n📊 Progresso: R$ {float(goal.current_amount):,.2f}."
        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_registrar_gasto(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        cat_name = str(data.get("category_name", "Outros"))
        amount = float(data.get("amount", 0))
        description = str(data.get("description", ""))

        if not amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Quanto você gastou?")
            return

        categories = await self.spending_repo.get_all_categories()
        cat = next((c for c in categories if c.name.lower() == cat_name.lower()), 
                   next((c for c in categories if c.name == "Outros"), categories[0]))

        spending = Spending(
            id=uuid4(), client_id=client_id, category_id=cat.id,
            amount=Decimal(str(amount)), description=description, spent_at=datetime.now()
        )
        await self.spending_repo.create_spending(spending)

        # Proactive Alert (Feature 1)
        await self.alerter.check_spending_alerts(client_id, phone, cat.id)

        msg = f"💸 *Gasto registrado!*\n\n📂 Categoria: *{cat.name}*\n💰 Valor: *R$ {amount:,.2f}*\n📝 Obs: {description or 'Nenhuma'}"
        buttons = [{"id": "G_PDF", "label": "📥 Ver Relatório"}, {"id": "RESUMO", "label": "📊 Resumo"}]
        await self._send_buttons_with_typing(phone, "Confirmado", msg, buttons, 1200)

    async def _orchestrate_simular_compra(self, phone: str, client_id: UUID, data: Dict[str, Any], summary: List[Dict[str, Any]], reply_text: str):
        item = str(data.get("item", "este item"))
        amount = float(data.get("amount", 0))
        
        if not amount:
            await self.evolution_client.send_text_message(phone, reply_text or "Quanto custaria?")
            return

        total_limit = sum([float(s['limit_amount']) for s in summary])
        total_spent = sum([float(s['total_spent']) for s in summary])
        available = total_limit - total_spent
        
        msg = f"🔍 *Análise: {item}*\n\nPreço: *R$ {amount:,.2f}*\nDisponível: *R$ {available:,.2f}*\n\n"
        if amount > available:
            msg += "🚨 *Aviso:* Isso vai te deixar no vermelho este mês."
        else:
            msg += "✅ *Veredito:* Cabe no seu orçamento."

        await self.evolution_client.send_buttons(phone, "Simulação", msg, [{"id": "OK", "label": "Entendido"}])

    async def _orchestrate_simular_poupanca(self, phone: str, data: Dict[str, Any], reply_text: str):
        amount = float(data.get("initial_amount", 0))
        monthly = float(data.get("monthly_amount", 0))
        months = int(data.get("months", 12))
        rate = float(data.get("interest_rate", 0.005))
        final_val = amount * (1 + rate)**months + monthly * (((1 + rate)**months - 1) / rate)
        await self.evolution_client.send_text_message(phone, f"📈 *Simulação*\nResultado após {months} meses: *R$ {final_val:,.2f}*.")

    async def _orchestrate_cancelar_objetivo(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        goal_title = str(data.get("goal_title", ""))
        # Correção: Usar Use Case GetGoals
        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)
        
        goal = next((g for g in goals if g.title.lower() == goal_title.lower()), None)
        if goal:
            goal.status = "cancelled"
            await self.goal_repo.update(goal)
            await self.evolution_client.send_text_message(phone, f"✅ Objetivo *{goal.title}* cancelado.")

    async def _orchestrate_listar_objetivos(self, phone: str, client_id: UUID):
        # 1. Bubble Intro
        await self._send_with_typing(phone, "🔍 *Buscando seus objetivos ativos...*", 1000)
        
        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)
        
        # 2. Bubble Data
        msg = "🎯 *Status dos seus Objetivos:*\n\n"
        if not goals: msg += "Você ainda não tem objetivos ativos."
        else:
            for g in goals:
                perc = (float(g.current_amount) / float(g.target_amount)) * 100
                msg += f"• *{g.title}*: {perc:.1f}% (R$ {float(g.current_amount):,.2f})\n"
        
        msg += await self._calculate_emergency_fund_coverage(client_id, goals)
        
        # 3. Bubble Final (Buttons)
        await self._send_buttons_with_typing(phone, "Objetivos", msg, [{"id": "G_PDF", "label": "📥 Relatório PDF"}], 1200)

    async def _calculate_emergency_fund_coverage(self, client_id: UUID, goals: List[Goal]) -> str:
        client = await self.client_repo.get_by_id(client_id)
        if not client or not client.monthly_income: return ""
        ef_goal = next((g for g in goals if "reserva" in g.title.lower() or "emergência" in g.title.lower()), None)
        if not ef_goal: return "\n💡 Sem Reserva de Emergência ainda."
        months = float(ef_goal.current_amount) / float(client.monthly_income)
        return f"\n🛡️ *Reserva:* {months:.1f} meses de cobertura."

    async def _orchestrate_resumo_mensal(self, phone: str, client_id: UUID, client_name: str, summary: List[Dict[str, Any]]):
        await self._send_with_typing(phone, f"📊 *Processando seu resumo, {client_name}...*", 1000)
        
        msg = "📈 *Resumo de Gastos por Categoria:*\n\n"
        for s in summary:
            perc = (float(s['total_spent']) / float(s['limit_amount'])) * 100 if s['limit_amount'] > 0 else 0
            msg += f"• *{s['category']}*: {perc:.1f}% (R$ {float(s['total_spent']):,.2f})\n"
        
        try:
            ai_res = await self.gemini_client.generate_response(f"Dê um insight sobre: {summary}")
            insight = ai_res.get('reply_text', '')
            if insight:
                msg += f"\n🧠 *AI Insight:* {insight}"
        except: pass

        await self._send_buttons_with_typing(phone, "Resumo", msg, [{"id": "G_PDF", "label": "📥 Baixar PDF"}], 1500)

    async def _orchestrate_gerar_relatorio(self, phone: str, client_id: UUID, client_name: str, summary: List[Dict[str, Any]], goals: List[Goal]):
        await self._send_with_typing(phone, "🚀 *Iniciando geração do Relatório de Elite...*", 1000)
        await self.evolution_client.send_presence(phone, "recording", 3000) # Simula 'processando'
        
        try:
            ai_res = await self.gemini_client.generate_response(f"Análise profunda para {client_name}: {summary}")
            insight = ai_res.get("reply_text", "Seu desempenho foi sólido.")
            
            pdf_path = await self.report_generator.generate_monthly_report(client_name, date.today(), summary, goals, insight)
            
            await asyncio.sleep(2)
            await self._send_with_typing(phone, "✅ *Relatório finalizado!* Enviando o arquivo...", 800)
            await self.evolution_client.send_document(phone, pdf_path, os.path.basename(pdf_path), "Seu guia estratégico. 📈")
        except Exception as e:
            logger.error(f"Erro no relatório: {e}")
            await self.evolution_client.send_text_message(phone, "Tive um problema ao gerar o PDF.")

    async def _orchestrate_definir_meta_mensal(self, phone: str, client_id: UUID, data: Dict[str, Any], reply_text: str):
        cat_name, limit = str(data.get("category_name", "")), float(data.get("limit_amount", 0))
        cat = await self.spending_repo.get_category_by_name(cat_name)
        if cat:
            await self.spending_repo.create_monthly_goal(MonthlyGoal(client_id=client_id, category_id=cat.id, year_month=date.today().replace(day=1), limit_amount=Decimal(str(limit))))
            await self.evolution_client.send_text_message(phone, f"✅ Meta R$ {limit:,.2f} para {cat_name}.")
