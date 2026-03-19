import json as json_lib
import re
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
from src.use_cases.register_spending import RegisterSpending
from src.use_cases.summarize_history import SummarizeHistory

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

    async def execute(self, phone: str, text: str, message_id: str = None, is_audio: bool = False, media_url: str = None):
        logger.info(f"Processando mensagem de {phone} (Audio={is_audio})...")
        
        # 0. Rate Limiting (Phase 3)
        usage = await self.redis_session.get_api_usage(phone)
        if usage >= 50:
            logger.warning(f"Rate limit atingido para {phone}")
            await self.evolution_client.send_text_message(
                phone, 
                "⚠️ Você atingiu seu limite diário de mensagens (50). Tente novamente amanhã para manter a saúde do sistema! 🚀"
            )
            return
        
        await self.redis_session.increment_api_usage(phone)

        # Transcrição se necessário
        if is_audio and message_id:
            try:
                audio_bytes = await self.evolution_client.download_media(message_id, media_url=media_url)
                text = await self.gemini_client.transcribe_audio(audio_bytes)
                logger.info(f"Áudio transcrito para: {text}")
            except Exception as e:
                logger.error(f"Erro ao processar áudio: {e}")
                await self.evolution_client.send_text_message(phone, "Tive um problema ao ouvir seu áudio. Pode tentar novamente ou digitar?")
                return

        # 1. Buscar cliente (Transação Rápida)
        async with self.uow:
            client = await GetClientByPhone(self.client_repo).execute(phone)
            
        if not client:
            await self.evolution_client.send_text_message(
                phone, 
                "Olá! Não encontrei seu cadastro. Por favor, entre em contato com o suporte para ativar seu assistente financeiro."
            )
            return

        # 2. Carregar sessão
        session = await self.redis_session.get_session(phone)
        
        # 2.1. Otimização de Histórico (Summarization Window)
        history = session.get("history", [])
        if len(history) > 10:
            summary = await SummarizeHistory(self.gemini_client).execute(history[:-2])
            # Correção de Role (Bug Crítico 400 Google API) e ausência de método
            new_history = [{"role": "user", "content": f"Contexto de nossas conversas passadas (Apenas lembre-se, não responda): {summary}"}]
            new_history.extend(history[-2:]) # Mantém as 2 últimas mensagens vivas
            session["history"] = new_history
            await self.redis_session.save_session(phone, session)
            logger.info(f"Histórico de {phone} sumarizado.")

        # 4. Preparar contexto para o LLM
        current_date = date.today()
        # Escopo Seguro para I/O
        async with self.uow:
            spendings_summary = await GetMonthlySpending(self.spending_repo).execute(client.id, current_date)
            goals = await GetGoals(self.goal_repo).execute(client.id)
            
        system_prompt = self.gemini_client.prompt_builder.build_system_prompt(
            client=client,
            monthly_goals=[],
            goals=goals,
            spendings_summary=spendings_summary
        )

        # 5. Analisar com Gemini e Agent Loop
        try:
            response, chat_session = await self.gemini_client.chat(
                system_instruction=system_prompt,
                history=session["history"],
                message=text
            )
            
            final_response_text = ""
            
            # Agent Loop (Iterando enquanto houver ferramentas)
            while True:
                has_tool_call = False
                
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        # Extrai function_call de forma segura
                        call = getattr(part, "function_call", None)
                        if call:
                            has_tool_call = True
                            # Despacha apenas o primeiro tool call iterativamente
                            result = await self._dispatch_tool_call(call.name, dict(call.args), client, phone, current_date)
                            response = await self.gemini_client.send_tool_response(chat_session, call.name, {"result": str(result)})
                            break # Envia resposta e processa nova response do LLM
                
                if not has_tool_call:
                    final_response_text = response.text
                    break
                    
        except Exception as e:
            logger.error(f"Erro ao chamar Gemini: {e}")
            await self.evolution_client.send_text_message(phone, "Desculpe, tive um problema técnico ao processar sua mensagem. Pode repetir?")
            return

        # 7. Enviar resposta ao usuário (Proteção contra Payload Vazio)
        final_response_text = self._clean_llm_response(final_response_text)
        final_response_text = final_response_text.strip() if final_response_text else "Ação concluuída."
        await self.evolution_client.send_text_message(phone, final_response_text)

        # 8. Atualizar Histórico
        await self.redis_session.add_history(phone, "user", text)
        await self.redis_session.add_history(phone, "assistant", final_response_text)

    def _clean_llm_response(self, text: str) -> str:
        """
        Garante que o texto final enviado ao usuário seja texto puro.
        Remove blocos markdown de código (```json...```) e extrai o campo 'response'
        caso o LLM tenha retornado JSON legado por inércia do histórico de sessão Redis.
        """
        if not text:
            return text
        cleaned = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()
        try:
            data = json_lib.loads(cleaned)
            if isinstance(data, dict) and "response" in data:
                return str(data["response"]).strip()
        except (json_lib.JSONDecodeError, TypeError):
            pass
        return cleaned

    async def _dispatch_tool_call(self, name: str, args: Dict, client: Any, phone: str, current_date: date) -> str:
        """
        Executa chamadas de ferramentas encapsulando no UnitOfWork apenas o tempo necessário de I/O de Banco.
        """
        logger.info(f"Executando Action {name} com args {args}")
        try:
            if name == "registrar_gasto":
                async with self.uow:
                    await RegisterSpending(self.spending_repo).execute(
                        client_id=client.id,
                        category_name=args["categoria"],
                        amount=Decimal(str(args["valor"])),
                        description=args.get("descricao")
                    )
                return "SUCESSO: Gasto registrado."

            elif name == "criar_objetivo":
                async with self.uow:
                    await CreateGoal(self.goal_repo).execute(
                        client.id,
                        args["title"],
                        Decimal(str(args["target_amount"])),
                        date.fromisoformat(args["deadline"]) if args.get("deadline") else None
                    )
                return "SUCESSO: Objetivo criado."

            elif name == "listar_objetivos":
                async with self.uow:
                    goals = await GetGoals(self.goal_repo).execute(client.id)
                if not goals: return "AVISO: Sem metas ativas."
                return "METAS: " + "; ".join([f"{g.title} = {g.current_amount}/{g.target_amount} (ID: {g.id})" for g in goals])

            elif name == "cancelar_objetivo":
                async with self.uow:
                    await CancelGoal(self.goal_repo).execute(args["objetivo_id"])
                return "SUCESSO: Objetivo excluido."

            elif name == "simular_compra":
                async with self.uow:
                    sim = await SimulatePurchase(self.spending_repo).execute(
                        client.id, args["item_name"], Decimal(str(args["price"])), current_date
                    )
                return f"RESULTADO Da COMPRA: Pode comprar={sim['can_buy']}. Limite sobrando após: {sim['remaining_limit']}."

            elif name == "obter_resumo_mensal":
                async with self.uow:
                    summary = await GetMonthlySpending(self.spending_repo).execute(client.id, current_date)
                total = sum(s["total_spent"] for s in summary)
                return f"RESULTADO DO MÊS: Total={total}. Distribuído: {str(summary)}."
                
        except Exception as e:
            logger.error(f"Erro em tool {name}: {e}")
            return f"ERRO: falha técnica ao executar. Motivo: {str(e)}"
            
        return "ERRO: Ferramenta não encontrada."
