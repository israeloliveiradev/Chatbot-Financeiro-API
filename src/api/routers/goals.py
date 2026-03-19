from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from decimal import Decimal
from datetime import date
from src.api.dependencies import get_client_repository, get_goal_repository, get_unit_of_work
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_goals import GetGoals
from src.api.schemas import StandardResponse, GoalResponse, GoalUpdateRequest

router = APIRouter(prefix="/goals", tags=["Objetivos Financeiros"])

async def _get_client_or_404(phone: str, client_repo: ClientRepository):
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client

@router.get("/{phone}", summary="Lista objetivos", response_model=StandardResponse)
async def list_goals(
    phone: str,
    client_repo: ClientRepository = Depends(get_client_repository),
    goal_repo: GoalRepository = Depends(get_goal_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    goals = await GetGoals(goal_repo).execute(client.id, only_active=True)

    data = [
        GoalResponse(
            id=str(g.id),
            title=g.title,
            target_amount=float(g.target_amount),
            current_amount=float(g.current_amount),
            status=g.status,
            deadline=g.deadline.isoformat() if g.deadline else None,
        ).model_dump()
        for g in goals
    ]
    return StandardResponse(data=data)

@router.patch("/{phone}/{goal_id}", summary="Atualiza objetivo", response_model=StandardResponse)
async def update_goal(
    phone: str,
    goal_id: UUID,
    request: GoalUpdateRequest,
    client_repo: ClientRepository = Depends(get_client_repository),
    goal_repo: GoalRepository = Depends(get_goal_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    await _get_client_or_404(phone, client_repo)
    goal = await goal_repo.get_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Objetivo não encontrado")

    if request.title is not None:
        goal.title = request.title
    if request.target_amount is not None:
        goal.target_amount = Decimal(str(request.target_amount))
    if request.deadline is not None:
        goal.deadline = date.fromisoformat(request.deadline)
    if request.status is not None:
        goal.status = request.status

    async with uow:
        saved = await goal_repo.update(goal)

    return StandardResponse(
        message="Objetivo atualizado com sucesso",
        data=GoalResponse(
            id=str(saved.id),
            title=saved.title,
            target_amount=float(saved.target_amount),
            current_amount=float(saved.current_amount),
            status=saved.status,
            deadline=saved.deadline.isoformat() if saved.deadline else None,
        ).model_dump(),
    )

@router.delete("/{phone}/{goal_id}", summary="Deleta objetivo", response_model=StandardResponse)
async def delete_goal(
    phone: str,
    goal_id: UUID,
    client_repo: ClientRepository = Depends(get_client_repository),
    goal_repo: GoalRepository = Depends(get_goal_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    await _get_client_or_404(phone, client_repo)
    async with uow:
        success = await goal_repo.delete(goal_id)

    if not success:
        raise HTTPException(status_code=404, detail="Objetivo não encontrado")

    return StandardResponse(message="Objetivo deletado com sucesso")
