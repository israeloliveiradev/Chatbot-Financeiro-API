from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from src.api.dependencies import get_client_repository, get_goal_repository, get_spending_repository
from src.domain.entities.client import Client
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_goals import GetGoals
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.adapters.repositories.client_repository import ClientRepositoryImpl
from src.adapters.repositories.goal_repository import GoalRepositoryImpl
from src.adapters.repositories.spending_repository import SpendingRepositoryImpl
from src.api.schemas import StandardResponse, ClientResponse, ClientCreateRequest, GoalResponse, SpendingSummaryResponse

router = APIRouter(prefix="/internal", tags=["Internal API"])

@router.get("/clients/{phone}", summary="Busca cliente", description="Busca um cliente pelo seu número de telefone (ex: 5511999999999).", response_model=StandardResponse)
async def get_client(
    phone: str,
    client_repo: ClientRepositoryImpl = Depends(get_client_repository)
):
    uc = GetClientByPhone(client_repo)
    client = await uc.execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    return StandardResponse(data=ClientResponse(
        id=str(client.id),
        phone=client.phone,
        name=client.name,
        monthly_income=float(client.monthly_income)
    ).model_dump())


@router.post("/clients", summary="Criar cliente", description="Cria um novo cliente na base. Retorna o cliente criado.", status_code=201, response_model=StandardResponse, responses={409: {"description": "Telefone já cadastrado"}})
async def create_client(
    request: ClientCreateRequest,
    client_repo: ClientRepositoryImpl = Depends(get_client_repository)
):
    uc = GetClientByPhone(client_repo)
    if await uc.execute(request.phone):
        raise HTTPException(status_code=409, detail="Telefone já cadastrado")
        
    client = Client(
        phone=request.phone,
        name=request.name,
        monthly_income=request.monthly_income
    )
    saved = await client_repo.create(client)
    
    return StandardResponse(message="Cliente criado", data=ClientResponse(
        id=str(saved.id),
        phone=saved.phone,
        name=saved.name,
        monthly_income=float(saved.monthly_income)
    ).model_dump())


@router.get("/clients/{phone}/goals", summary="Lista objetivos", description="Lista objetivos ativos do cliente.", response_model=StandardResponse)
async def list_goals(
    phone: str,
    client_repo: ClientRepositoryImpl = Depends(get_client_repository),
    goal_repo: GoalRepositoryImpl = Depends(get_goal_repository)
):
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    goals = await GetGoals(goal_repo).execute(client.id, only_active=True)
    
    data = [GoalResponse(
        id=str(g.id),
        title=g.title,
        target_amount=float(g.target_amount),
        current_amount=float(g.current_amount),
        status=g.status,
        deadline=g.deadline.isoformat() if g.deadline else None
    ).model_dump() for g in goals]
    
    return StandardResponse(data=data)


@router.get("/clients/{phone}/spending", summary="Resumo de gastos", description="Resumo de gastos do mês atual.", response_model=StandardResponse)
async def list_spending(
    phone: str,
    client_repo: ClientRepositoryImpl = Depends(get_client_repository),
    spending_repo: SpendingRepositoryImpl = Depends(get_spending_repository)
):
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
    summary = await GetMonthlySpending(spending_repo).execute(client.id, date.today())
    
    return StandardResponse(data=summary)
