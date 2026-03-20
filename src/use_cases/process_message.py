import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, Optional
import difflib

from src.adapters.llm.gemini_client import GeminiClient
from src.adapters.llm.prompt_builder import PromptBuilder
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.messaging.formatter import MessageFormatter
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.contribution_repository import ContributionRepository
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
        # 1. Transcrição se for áudio
        if is_audio and not text:
            audio_bytes = None
            if media_url:
                try:
                    logger.info(f"Baixando áudio da URL: {media_url}")
                    audio_bytes = await self.evolution_client.download_media(media_url)
                except Exception as e:
                    logger.error(f"Erro ao baixar áudio: {e}")

            if audio_bytes:
                text = await self.gemini_client.transcribe_audio(audio_bytes, "audio/ogg")

            if not text:
                error_msg = MessageFormatter.error(
                    "Não consegui processar seu áudio. Pode digitar o que precisa ou tentar novamente? 🧐"
                )
                await self.evolution_client.send_text_message(phone, error_msg)
                return

        # 2. Busca contexto do cliente
        logger.info(f"[PROCESS] Iniciando busca de cliente para o número: {phone}")
        client = await GetClientByPhone(self.client_repo).execute(phone)
        if not client:
            logger.warning(f"[PROCESS] Cliente NÃO encontrado no banco para o número: {phone}")
            msg = MessageFormatter.header("Bem-vindo!")
            msg += (
                "Olá! Sou seu assistente financeiro pessoal. 👋\n\n"
                "No momento, ainda não encontrei seu cadastro no nosso sistema. "
                "Por favor, entre em contato com o suporte ou realize o cadastro "
                "via painel para começarmos a organizar suas finanças! 😉"
            )
            msg += MessageFormatter.footer()
            await self.evolution_client.send_text_message(phone, msg)
            return

        # 3. Busca objetivos e resumos
        goals = await GetGoals(self.goal_repo).execute(client.id, only_active=True)
        spendings_summary = await GetMonthlySpending(self.spending_repo).execute(
            client.id, date.today()
        )

        history = []  # TODO: Buscar histórico real do Redis/banco

        # 4. Reconhecimento de Intent via Gemini
        prompt = self.prompt_builder.build_system_prompt(
            client_name=client.name,
            monthly_income=float(client.monthly_income),
            goals=[g.__dict__ for g in goals],
            spendings_summary=spendings_summary,
            history=history,
        )

        full_prompt = f"{prompt}\n\nMENSAGEM DO USUÁRIO: {text}"

        try:
            raw_response = await self.gemini_client.analyze_message(full_prompt)
            # 4. Processamento da Resposta do Gemini
            if not raw_response:
                raise ValueError("Gemini retornou resposta vazia")

            # 4.1 Parser de Resposta (Resiliência a erros de JSON)
            if isinstance(raw_response, dict):
                response_data = raw_response
            else:
                try:
                    # Limpa possíveis backticks de markdown
                    clean_json = str(raw_response).replace("```json", "").replace("```", "").strip()
                    response_data = json.loads(clean_json)
                except json.JSONDecodeError:
                    logger.warning(f"[PROCESS] Falha ao decodificar JSON. Tratando como conversa: {raw_response}")
                    response_data = {
                        "intent": "conversa",
                        "extracted_data": {},
                        "reply_text": str(raw_response)
                    }
        except Exception as e:
            logger.error(f"Erro crítico ao processar resposta: {e}")
            await self.evolution_client.send_text_message(
                phone, "Desculpe, tive um problema técnico. Pode tentar novamente? 😅"
            )
            return

        intent = response_data.get("intent", "conversa")
        reply_text = response_data.get("reply_text", "")
        extracted_data = response_data.get("extracted_data", {})

        logger.info(f"[PROCESS] Intent: {intent} | Data: {extracted_data}")

        # 5. Orquestração de Ações
        if intent == "criar_objetivo":
            await self._orchestrate_criar_objetivo(
                phone, client.id, extracted_data, reply_text
            )
        elif intent == "registrar_aporte":
            await self._orchestrate_registrar_aporte(
                phone, client.id, extracted_data, reply_text
            )
        elif intent == "simular_poupanca":
            await self._orchestrate_simular_poupanca(phone, extracted_data, reply_text)
        elif intent == "cancelar_objetivo":
            await self._orchestrate_cancelar_objetivo(
                phone, client.id, extracted_data, reply_text
            )
        elif intent == "listar_objetivos":
            await self._orchestrate_listar_objetivos(phone, client.id)
        elif intent == "obter_resumo_mensal":
            await self._orchestrate_resumo_mensal(
                phone, client.id, client.name, spendings_summary
            )
        elif intent == "definir_meta_mensal":
            await self._orchestrate_definir_meta_mensal(
                phone, client.id, extracted_data, reply_text
            )
        elif intent in ("registrar_gasto", "simular_compra"):
            await self._orchestrate_simular_compra(
                phone, extracted_data, spendings_summary, reply_text
            )
        else:
            # Conversa genérica
            if reply_text:
                await self.evolution_client.send_text_message(phone, reply_text)
            else:
                await self.evolution_client.send_text_message(
                    phone, "Em que posso ajudar? 😊"
                )

    # ─────────────────────────────────────────────────────
    # Orquestradores
    # ─────────────────────────────────────────────────────

    async def _orchestrate_criar_objetivo(
        self, phone: str, client_id: Any, data: Dict[str, Any], reply_text: str
    ):
        title = data.get("title", "")
        target_amount = data.get("target_amount", 0)
        deadline_str = data.get("deadline", "")

        if not title or not target_amount:
            msg = reply_text or "Para criar um objetivo preciso do nome e do valor. Pode me informar? 🎯"
            await self.evolution_client.send_text_message(phone, msg)
            return

        # Parse deadline
        deadline = None
        if deadline_str:
            try:
                # Aceitar formatos: "2026-12", "2026-12-03", "12/2026", "03/12/2026", etc.
                for fmt in ("%Y-%m-%d", "%Y-%m", "%d/%m/%Y", "%m/%Y"):
                    try:
                        deadline = datetime.strptime(deadline_str, fmt).date()
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        # Cria o Goal
        from uuid import uuid4

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

        deadline_fmt = deadline.strftime("%d/%m/%Y") if deadline else "sem prazo definido"
        msg = (
            f"✅ *Objetivo criado com sucesso!*\n\n"
            f"🎯 *{title}*\n"
            f"💰 Meta: R$ {float(target_amount):,.2f}\n"
            f"📅 Prazo: {deadline_fmt}\n"
        )
        if reply_text:
            msg += f"\n{reply_text}"

        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_registrar_aporte(
        self, phone: str, client_id: Any, data: Dict[str, Any], reply_text: str
    ):
        goal_title = data.get("goal_title")
        amount = data.get("amount")

        if not goal_title or not amount:
            await self.evolution_client.send_text_message(
                phone,
                reply_text or "Para registrar um aporte, preciso do nome do objetivo e do valor. 💰",
            )
            return

        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)
        if not goals:
            await self.evolution_client.send_text_message(
                phone,
                "Você não tem nenhum objetivo ativo para guardar dinheiro. Quer criar um? 🎯",
            )
            return

        # Fuzzy matching
        goal_names = [g.title for g in goals]
        matches = difflib.get_close_matches(goal_title, goal_names, n=1, cutoff=0.4)

        if not matches:
            await self.evolution_client.send_text_message(
                phone,
                f"Não encontrei nenhum objetivo parecido com '{goal_title}'. Pode confirmar o nome? 🧐",
            )
            return

        target_goal = next(g for g in goals if g.title == matches[0])

        uc = RegisterContribution(self.contribution_repo, self.goal_repo)
        await uc.execute(target_goal.id, Decimal(str(amount)))

        new_amount = float(target_goal.current_amount) + float(amount)
        progress = (new_amount / float(target_goal.target_amount)) * 100 if float(target_goal.target_amount) > 0 else 0

        msg = (
            f"✅ *Aporte registrado!*\n\n"
            f"🎯 *{target_goal.title}*\n"
            f"💰 Aporte: R$ {float(amount):,.2f}\n"
            f"📊 Progresso: R$ {new_amount:,.2f} / R$ {float(target_goal.target_amount):,.2f} ({progress:.1f}%)\n"
        )
        if reply_text:
            msg += f"\n{reply_text}"

        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_simular_poupanca(
        self, phone: str, data: Dict[str, Any], reply_text: str
    ):
        target_amount = data.get("target_amount")
        monthly_saving = data.get("monthly_saving")

        if not target_amount or not monthly_saving:
            await self.evolution_client.send_text_message(
                phone,
                reply_text
                or "Para simular, preciso do valor total e de quanto você pretende guardar por mês. 📊",
            )
            return

        uc = SimulateSavings()
        result = await uc.execute(
            Decimal(str(target_amount)), Decimal(str(monthly_saving)), date.today()
        )

        if result["possible"]:
            est_date = datetime.fromisoformat(result["estimated_date"]).strftime("%m/%Y")
            msg = (
                f"📊 *Simulação de Poupança*\n\n"
                f"Para juntar R$ {float(target_amount):,.2f} guardando R$ {float(monthly_saving):,.2f}/mês:\n"
                f"⏱️ Tempo: {result['months_needed']} meses\n"
                f"📅 Data prevista: {est_date}\n"
            )
        else:
            msg = f"❌ Não consegui simular: {result.get('reason')}"

        if reply_text:
            msg += f"\n\n{reply_text}"

        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_cancelar_objetivo(
        self, phone: str, client_id: Any, data: Dict[str, Any], reply_text: str
    ):
        goal_title = data.get("goal_title")
        if not goal_title:
            await self.evolution_client.send_text_message(
                phone, reply_text or "Qual objetivo você quer cancelar? 🤔"
            )
            return

        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)
        goal_names = [g.title for g in goals]
        matches = difflib.get_close_matches(goal_title, goal_names, n=1, cutoff=0.5)

        if matches:
            target_goal = next(g for g in goals if g.title == matches[0])
            target_goal.status = "cancelled"
            await self.goal_repo.update(target_goal)

            msg = (
                f"🗑️ *Objetivo cancelado!*\n\n"
                f"O objetivo *{matches[0]}* foi cancelado com sucesso."
            )
            if reply_text:
                msg += f"\n\n{reply_text}"
            await self.evolution_client.send_text_message(phone, msg)
        else:
            await self.evolution_client.send_text_message(
                phone,
                reply_text
                or f"Não encontrei nenhum objetivo parecido com '{goal_title}'. 🧐",
            )

    async def _orchestrate_listar_objetivos(self, phone: str, client_id: Any):
        goals = await GetGoals(self.goal_repo).execute(client_id, only_active=True)

        if not goals:
            await self.evolution_client.send_text_message(
                phone,
                "Você ainda não tem nenhum objetivo ativo. Quer criar um? 🎯",
            )
            return

        msg = "🎯 *Seus Objetivos Ativos:*\n\n"
        for g in goals:
            progress = (
                (float(g.current_amount) / float(g.target_amount)) * 100
                if float(g.target_amount) > 0
                else 0
            )
            deadline_str = g.deadline.strftime("%d/%m/%Y") if g.deadline else "sem prazo"
            msg += (
                f"▫️ *{g.title}*\n"
                f"   R$ {float(g.current_amount):,.2f} / R$ {float(g.target_amount):,.2f} ({progress:.1f}%)\n"
                f"   📅 {deadline_str}\n\n"
            )

        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_resumo_mensal(
        self,
        phone: str,
        client_id: Any,
        client_name: str,
        spendings_summary: list,
    ):
        if not spendings_summary:
            await self.evolution_client.send_text_message(
                phone,
                f"📊 *Resumo Mensal*\n\nNenhuma meta de gasto definida para este mês, {client_name}. "
                f"Quer definir limites de gasto por categoria? 💡",
            )
            return

        total_limit = sum(s["limit_amount"] for s in spendings_summary)
        total_spent = sum(s["total_spent"] for s in spendings_summary)

        msg = f"📊 *Resumo Mensal — {date.today().strftime('%B/%Y')}*\n\n"

        for s in spendings_summary:
            pct = (
                (s["total_spent"] / s["limit_amount"]) * 100
                if s["limit_amount"] > 0
                else 0
            )
            bar = "🟢" if pct < 80 else ("🟡" if pct < 100 else "🔴")
            msg += (
                f"{bar} *{s['category']}*\n"
                f"   Gasto: R$ {s['total_spent']:,.2f} / R$ {s['limit_amount']:,.2f} ({pct:.0f}%)\n"
                f"   Disponível: R$ {s['available']:,.2f}\n\n"
            )

        msg += f"💰 *Total:* R$ {total_spent:,.2f} / R$ {total_limit:,.2f}"

        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_definir_meta_mensal(
        self, phone: str, client_id: Any, data: Dict[str, Any], reply_text: str
    ):
        category_name = data.get("category_name", "")
        limit_amount = data.get("limit_amount", 0)

        if not category_name or not limit_amount:
            msg = (
                reply_text
                or "Para definir uma meta mensal preciso da categoria e do limite. Exemplo: "
                '"Quero gastar no máximo R$ 500 em Alimentação" 🍽️'
            )
            await self.evolution_client.send_text_message(phone, msg)
            return

        # Buscar ou criar categoria
        category = await self.spending_repo.get_category_by_name(category_name)
        if not category:
            from src.domain.entities.spending_category import SpendingCategory
            from uuid import uuid4

            category = SpendingCategory(id=uuid4(), name=category_name)
            await self.spending_repo.create_category(category)

        # Verificar se já existe meta para este mês
        year_month = date.today().replace(day=1)
        existing = await self.spending_repo.get_monthly_goal(
            client_id, category.id, year_month
        )

        if existing:
            existing.limit_amount = Decimal(str(limit_amount))
            await self.spending_repo.update_monthly_goal(existing)
            action = "atualizada"
        else:
            from src.domain.entities.monthly_goal import MonthlyGoal
            from uuid import uuid4

            mg = MonthlyGoal(
                id=uuid4(),
                client_id=client_id,
                category_id=category.id,
                year_month=year_month,
                limit_amount=Decimal(str(limit_amount)),
            )
            await self.spending_repo.create_monthly_goal(mg)
            action = "criada"

        msg = (
            f"✅ *Meta mensal {action}!*\n\n"
            f"📁 Categoria: *{category_name}*\n"
            f"💰 Limite: R$ {float(limit_amount):,.2f}/mês\n"
        )
        if reply_text:
            msg += f"\n{reply_text}"

        await self.evolution_client.send_text_message(phone, msg)

    async def _orchestrate_simular_compra(
        self,
        phone: str,
        data: Dict[str, Any],
        spendings_summary: list,
        reply_text: str,
    ):
        amount = data.get("amount", 0)
        category_name = data.get("category_name", "")

        if not amount or not category_name:
            msg = (
                reply_text
                or "Para simular uma compra, me diga o valor e a categoria. "
                'Exemplo: "Posso gastar R$ 200 em Lazer?" 🛍️'
            )
            await self.evolution_client.send_text_message(phone, msg)
            return

        # Procura a categoria no resumo de gastos
        match = None
        for s in spendings_summary:
            if s["category"].lower() == category_name.lower():
                match = s
                break

        if not match:
            # Categoria sem meta mensal definida
            msg = (
                f"Você não tem uma meta mensal para *{category_name}*.\n"
                f"O gasto de R$ {float(amount):,.2f} seria registrado sem limite definido.\n"
                f"Quer definir uma meta mensal para essa categoria? 💡"
            )
        else:
            new_total = match["total_spent"] + float(amount)
            available_after = match["limit_amount"] - new_total

            if available_after >= 0:
                msg = (
                    f"✅ *Compra viável!*\n\n"
                    f"🛍️ *{category_name}*: R$ {float(amount):,.2f}\n"
                    f"📊 Gasto atual: R$ {match['total_spent']:,.2f}\n"
                    f"📊 Gasto após compra: R$ {new_total:,.2f} / R$ {match['limit_amount']:,.2f}\n"
                    f"💰 Sobraria: R$ {available_after:,.2f}\n"
                )
            else:
                msg = (
                    f"⚠️ *Compra acima do orçamento!*\n\n"
                    f"🛍️ *{category_name}*: R$ {float(amount):,.2f}\n"
                    f"📊 Gasto atual: R$ {match['total_spent']:,.2f}\n"
                    f"📊 Limite: R$ {match['limit_amount']:,.2f}\n"
                    f"🔴 Estouraria em: R$ {abs(available_after):,.2f}\n"
                )

        if reply_text:
            msg += f"\n{reply_text}"

        await self.evolution_client.send_text_message(phone, msg)
