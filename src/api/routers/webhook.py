from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from typing import Any, Dict

from src.infra.config import settings
from src.api.dependencies import (
    get_webhook_parser, get_evolution_client, get_redis_session, get_gemini_client,
    get_client_repository, get_spending_repository, get_goal_repository, get_contribution_repository
)
from src.adapters.messaging.webhook_parser import WebhookParser
from src.adapters.messaging.evolution_client import EvolutionClient
from src.adapters.cache.redis_session import RedisSession
from src.adapters.llm.gemini_client import GeminiClient
from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.contribution_repository import ContributionRepositoryImpl

from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.use_cases.get_goals import GetGoals
from src.use_cases.create_goal import CreateGoal
from src.use_cases.register_contribution import RegisterContribution
from src.use_cases.cancel_goal import CancelGoal
from src.use_cases.simulate_purchase import SimulatePurchase
from src.use_cases.simulate_savings import SimulateSavings

router = APIRouter(tags=["Webhook"])


async def process_user_message(
    phone: str,
    text: str,
    client_repo: ClientRepositoryImpl,
    spending_repo: SpendingRepositoryImpl,
    goal_repo: GoalRepositoryImpl,
    contribution_repo: ContributionRepositoryImpl,
    redis_session: RedisSession,
    evolution_client: EvolutionClient,
    gemini_client: GeminiClient,
):
    # 3. Buscar client no banco
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        await evolution_client.send_text_message(phone, "Oi! Seu número ainda não está cadastrado na nossa base. Fale com seu planejador financeiro.")
        return

    # 4. Carregar sessão (Redis)
    session = await redis_session.get_session(phone)
    
    # 5. Lidar com action pendente (Sim/Não)
    pending_action = session.get("pending_action")
    if pending_action:
        lower_txt = text.lower().strip()
        if lower_txt in ["sim", "s", "confirmo", "isso"]:
            if pending_action == "confirm_create_goal":
                data = session["pending_data"]
                try:
                    await CreateGoal(goal_repo).execute(
                        client.id, 
                        data["title"], 
                        Decimal(data["target_amount"]), 
                        date.fromisoformat(data["deadline"]) if data.get("deadline") else None
                    )
                    await evolution_client.send_text_message(phone, f"Prontinho! Criei o objetivo '{data['title']}'.")
                except Exception as e:
                    await evolution_client.send_text_message(phone, f"Putz, deu um erro ao criar a meta. Tente novamente.")
            
            elif pending_action == "confirm_cancel_goal":
                data = session["pending_data"]
                await CancelGoal(goal_repo).execute(data["goal_id"])
                await evolution_client.send_text_message(phone, "Objetivo cancelado com sucesso.")
        else:
            await evolution_client.send_text_message(phone, "Ação cancelada.")
            
        await redis_session.clear_pending_action(phone)
        return

    # 6. Agrupar dados pro LLM
    current_date = date.today()
    spendings_summary = await GetMonthlySpending(spending_repo).execute(client.id, current_date)
    goals = await GetGoals(goal_repo).execute(client.id)
    
    # Montar o System Prompt
    system_prompt = gemini_client.prompt_builder.build_system_prompt(
        client=client,
        monthly_goals=[], # Já incluso no spendings_summary pro LLM
        goals=goals,
        spendings_summary=spendings_summary
    )

    # Chamar LLM
    llm_result = await gemini_client.analyze_message(
        system_prompt=system_prompt,
        history=session["history"],
        current_message=text
    )

    intent = llm_result.get("intent")
    data = llm_result.get("extracted_data", {})
    response_text = llm_result.get("response", "Não entendi muito bem. Pode reformular?")
    
    # Executar Use Cases baseados no Intent
    if intent == "criar_objetivo":
        title = data.get("title")
        target_amount = data.get("target_amount")
        if title and target_amount:
            await redis_session.set_pending_action(phone, "confirm_create_goal", data)
            # Response_text já deve vir do LLM perguntando a confirmação

    elif intent == "registrar_aporte":
        # Tentaria buscar nos dados qual o goal exato usando a string, aqui simplifico
        # pois o LLM precisa devolver algo que dê match (idealmente o frontend listaria UUIDs).
        # Assumindo que o LLM só narrou e a gente faria a baixa, vou apenas repassar a resposta.
        # Em um cenário real, o LLM extrairia o "title" e bateríamos com os goals para achar o ID.
        pass
        
    elif intent == "simular_compra":
        cat = data.get("category")
        amount = data.get("purchase_amount")
        if cat and amount:
            sim_res = await SimulatePurchase(spending_repo).execute(client.id, cat, Decimal(str(amount)), current_date)
            if not sim_res["can_buy"]:
                response_text = f"Cuidado! O limite atual disponível em {sim_res.get('category', cat)} não comporta R$ {amount}."

    elif intent == "simular_poupanca":
        pass # LLM apenas responde baseado no prompt instrucional
    
    # 7+8. Atualizar Histórico e enviar Mensagem
    await redis_session.add_history(phone, "user", text)
    await redis_session.add_history(phone, "assistant", response_text)
    
    await evolution_client.send_text_message(phone, response_text)


@router.post("/webhook/evolution", summary="Recebe mensagens", description="Recebe mensagens da Evolution API WhatsApp")
async def evolution_webhook(
    request: Request,
    parser: WebhookParser = Depends(get_webhook_parser),
    evolution_client: EvolutionClient = Depends(get_evolution_client),
    redis_session: RedisSession = Depends(get_redis_session),
    gemini_client: GeminiClient = Depends(get_gemini_client),
    client_repo: ClientRepositoryImpl = Depends(get_client_repository),
    spending_repo: SpendingRepositoryImpl = Depends(get_spending_repository),
    goal_repo: GoalRepositoryImpl = Depends(get_goal_repository),
    contribution_repo: ContributionRepositoryImpl = Depends(get_contribution_repository)
):
    payload = await request.json()
    msg = parser.parse_upsert_message(payload)
    
    if not msg:
        return {"status": "ignored"}
        
    # Processa em background (ou não, se o FastAPI suportar e não fechar a task) 
    # pro webhook responder OK rapidamente e não gargalar.
    # Mas aqui faremos síncrono para garantir o fluxo até adicionarmos BackgroundTasks se necessário
    await process_user_message(
        msg.phone, msg.text, client_repo, spending_repo, goal_repo, contribution_repo,
        redis_session, evolution_client, gemini_client
    )
    
    return {"status": "ok"}


if settings.app_env == "development":
    from pydantic import BaseModel
    
    class SimulateMessageRequest(BaseModel):
        phone: str
        text: str

    @router.post("/dev/simulate-message", tags=["Dev / Testes"], summary="Simulador (DEV ONLY)", description="Simula entrada de mensagem de texto no fluxo")
    async def simulate_message(
        req: SimulateMessageRequest,
        evolution_client: EvolutionClient = Depends(get_evolution_client),
        redis_session: RedisSession = Depends(get_redis_session),
        gemini_client: GeminiClient = Depends(get_gemini_client),
        client_repo: ClientRepositoryImpl = Depends(get_client_repository),
        spending_repo: SpendingRepositoryImpl = Depends(get_spending_repository),
        goal_repo: GoalRepositoryImpl = Depends(get_goal_repository),
        contribution_repo: ContributionRepositoryImpl = Depends(get_contribution_repository)
    ):
        await process_user_message(
            req.phone, req.text, client_repo, spending_repo, goal_repo, contribution_repo,
            redis_session, evolution_client, gemini_client
        )
        return {"status": "simulated"}
