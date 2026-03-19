from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import (
    get_client_repository,
    get_goal_repository,
    get_spending_repository,
    get_unit_of_work,
)
from src.domain.entities.client import Client
from src.domain.entities.goal import Goal
from src.domain.entities.monthly_goal import MonthlyGoal
from src.domain.entities.spending import Spending
from src.domain.entities.spending_category import SpendingCategory
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.goal_repository import GoalRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_goals import GetGoals
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.api.schemas import (
    StandardResponse,
    ClientResponse,
    ClientCreateRequest,
    GoalResponse,
    GoalUpdateRequest,
    SpendingSummaryResponse,
    TransactionCreateRequest,
    TransactionResponse,
    MonthlyGoalCreateRequest,
    MonthlyGoalResponse,
    CategoryCreateRequest,
    CategoryResponse,
)

router = APIRouter(prefix="/internal", tags=["Internal API"])


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_client_or_404(phone: str, client_repo: ClientRepository) -> Client:
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


# ── Clients ──────────────────────────────────────────────────────────────────

@router.get(
    "/clients/{phone}",
    summary="Busca cliente",
    description="Busca um cliente pelo número de telefone (ex: 5511999999999).",
    response_model=StandardResponse,
)
async def get_client(
    phone: str,
    client_repo: ClientRepository = Depends(get_client_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    return StandardResponse(
        data=ClientResponse(
            id=str(client.id),
            phone=client.phone,
            name=client.name,
            monthly_income=float(client.monthly_income),
        ).model_dump()
    )


@router.post(
    "/clients",
    summary="Criar cliente",
    description="Cria um novo cliente. Retorna 409 se o telefone já estiver cadastrado.",
    status_code=201,
    response_model=StandardResponse,
    responses={409: {"description": "Telefone já cadastrado"}},
)
async def create_client(
    request: ClientCreateRequest,
    client_repo: ClientRepository = Depends(get_client_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    if await GetClientByPhone(client_repo).execute(request.phone):
        raise HTTPException(status_code=409, detail="Telefone já cadastrado")

    client = Client(
        phone=request.phone,
        name=request.name,
        monthly_income=Decimal(str(request.monthly_income)),
    )

    async with uow:
        saved = await client_repo.create(client)

    return StandardResponse(
        message="Cliente criado com sucesso",
        data=ClientResponse(
            id=str(saved.id),
            phone=saved.phone,
            name=saved.name,
            monthly_income=float(saved.monthly_income),
        ).model_dump(),
    )


# ── Goals ─────────────────────────────────────────────────────────────────────

@router.get(
    "/clients/{phone}/goals",
    summary="Lista objetivos",
    description="Lista objetivos ativos do cliente.",
    response_model=StandardResponse,
)
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


@router.patch(
    "/clients/{phone}/goals/{goal_id}",
    summary="Atualiza objetivo",
    description="Atualiza campos de um objetivo existente.",
    response_model=StandardResponse,
)
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


@router.delete(
    "/clients/{phone}/goals/{goal_id}",
    summary="Deleta objetivo",
    description="Remove permanentemente um objetivo.",
    response_model=StandardResponse,
)
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


# ── Monthly Goals (orçamento por categoria) ───────────────────────────────────

@router.post(
    "/clients/{phone}/monthly-goals",
    summary="Definir meta mensal",
    description=(
        "Define (cria ou atualiza) o limite mensal de gasto para uma categoria. "
        "Se já existir uma meta para o mesmo mês e categoria, retorna 409."
    ),
    status_code=201,
    response_model=StandardResponse,
    responses={404: {"description": "Cliente ou categoria não encontrada"}, 409: {"description": "Meta já existe para esse mês/categoria"}},
)
async def create_monthly_goal(
    phone: str,
    request: MonthlyGoalCreateRequest,
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    client = await _get_client_or_404(phone, client_repo)

    category = await spending_repo.get_category_by_name(request.category_name)
    if not category:
        categories = await spending_repo.get_all_categories()
        cat_list = ", ".join(c.name for c in categories)
        raise HTTPException(
            status_code=404,
            detail=f"Categoria '{request.category_name}' não encontrada. Disponíveis: {cat_list}",
        )

    # Normaliza para dia 1 do mês
    try:
        parsed = datetime.strptime(request.year_month, "%Y-%m").date()
        normalized = parsed.replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail="year_month deve estar no formato YYYY-MM")

    # Verifica se já existe meta para esse mês/categoria
    existing = await spending_repo.get_monthly_goal(client.id, category.id, normalized)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe uma meta para '{request.category_name}' em {request.year_month}. Nenhum endpoint de update foi implementado — delete e recrie.",
        )

    monthly_goal = MonthlyGoal(
        client_id=client.id,
        category_id=category.id,
        year_month=normalized,
        limit_amount=Decimal(str(request.limit_amount)),
    )

    async with uow:
        saved = await spending_repo.create_monthly_goal(monthly_goal)

    return StandardResponse(
        message="Meta mensal criada com sucesso",
        data=MonthlyGoalResponse(
            id=str(saved.id),
            category_name=category.name,
            limit_amount=float(saved.limit_amount),
            year_month=saved.year_month.strftime("%Y-%m"),
            alert_80_sent=saved.alert_80_sent,
            alert_100_sent=saved.alert_100_sent,
        ).model_dump(),
    )


@router.get(
    "/clients/{phone}/monthly-goals",
    summary="Lista metas mensais",
    description="Lista todas as metas mensais de gasto do mês atual.",
    response_model=StandardResponse,
)
async def list_monthly_goals(
    phone: str,
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    normalized = date.today().replace(day=1)
    goals = await spending_repo.get_monthly_goals_by_client_and_month(client.id, normalized)
    categories = await spending_repo.get_all_categories()
    cat_map = {c.id: c.name for c in categories}

    data = [
        MonthlyGoalResponse(
            id=str(g.id),
            category_name=cat_map.get(g.category_id, "Desconhecida"),
            limit_amount=float(g.limit_amount),
            year_month=g.year_month.strftime("%Y-%m"),
            alert_80_sent=g.alert_80_sent,
            alert_100_sent=g.alert_100_sent,
        ).model_dump()
        for g in goals
    ]
    return StandardResponse(data=data)


# ── Spending (Gastos/Transações) ──────────────────────────────────────────────

@router.post(
    "/clients/{phone}/transactions",
    summary="Registrar gasto (transação)",
    description=(
        "Lança manualmente uma transação de gasto para o cliente. "
        "A categoria deve existir no sistema. Use GET /internal/categories para listar."
    ),
    status_code=201,
    response_model=StandardResponse,
    responses={404: {"description": "Cliente ou categoria não encontrada"}},
)
async def create_transaction(
    phone: str,
    request: TransactionCreateRequest,
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    client = await _get_client_or_404(phone, client_repo)

    category = await spending_repo.get_category_by_name(request.category_name)
    if not category:
        categories = await spending_repo.get_all_categories()
        cat_list = ", ".join(c.name for c in categories)
        raise HTTPException(
            status_code=404,
            detail=f"Categoria '{request.category_name}' não encontrada. Disponíveis: {cat_list}",
        )

    spent_at = request.spent_at or datetime.now(tz=timezone.utc)

    spending = Spending(
        client_id=client.id,
        category_id=category.id,
        amount=Decimal(str(request.amount)),
        description=request.description,
        spent_at=spent_at,
    )

    async with uow:
        saved = await spending_repo.create_spending(spending)

    return StandardResponse(
        message="Transação registrada com sucesso",
        data=TransactionResponse(
            id=str(saved.id),
            category_id=str(saved.category_id),
            category_name=category.name,
            amount=float(saved.amount),
            description=saved.description,
            spent_at=saved.spent_at.isoformat(),
        ).model_dump(),
    )


@router.get(
    "/clients/{phone}/transactions",
    summary="Lista transações do mês",
    description="Lista todos os gastos registrados para o cliente no mês atual.",
    response_model=StandardResponse,
)
async def list_transactions(
    phone: str,
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    spendings = await spending_repo.get_spendings_by_client_and_month(client.id, date.today())
    categories = await spending_repo.get_all_categories()
    cat_map = {c.id: c.name for c in categories}

    data = [
        TransactionResponse(
            id=str(s.id),
            category_id=str(s.category_id),
            category_name=cat_map.get(s.category_id, "Desconhecida"),
            amount=float(s.amount),
            description=s.description,
            spent_at=s.spent_at.isoformat(),
        ).model_dump()
        for s in spendings
    ]
    return StandardResponse(data=data)


# ── Spending Summary ──────────────────────────────────────────────────────────

@router.get(
    "/clients/{phone}/spending",
    summary="Resumo de gastos",
    description="Resumo de gastos vs. metas do mês atual, por categoria.",
    response_model=StandardResponse,
)
async def list_spending_summary(
    phone: str,
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    summary = await GetMonthlySpending(spending_repo).execute(client.id, date.today())
    return StandardResponse(data=summary)


# ── Categories ────────────────────────────────────────────────────────────────

@router.get(
    "/categories",
    summary="Lista categorias",
    description="Lista todas as categorias de gastos cadastradas no sistema.",
    response_model=StandardResponse,
)
async def list_categories(
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    categories = await spending_repo.get_all_categories()
    data = [{"id": str(c.id), "name": c.name} for c in categories]
    return StandardResponse(data=data)


@router.post(
    "/categories",
    summary="Criar categoria",
    description="Cria uma nova categoria de gastos.",
    status_code=201,
    response_model=StandardResponse,
)
async def create_category(
    request: CategoryCreateRequest,
    spending_repo: SpendingRepository = Depends(get_spending_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    existing = await spending_repo.get_category_by_name(request.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Categoria '{request.name}' já existe")

    category = SpendingCategory(name=request.name)
    async with uow:
        saved = await spending_repo.create_category(category)

    return StandardResponse(
        message="Categoria criada com sucesso",
        data=CategoryResponse(id=str(saved.id), name=saved.name).model_dump(),
    )


@router.delete(
    "/categories/{category_id}",
    summary="Deleta categoria",
    description="Remove uma categoria. Falhará se houver gastos ou metas vinculadas.",
    response_model=StandardResponse,
)
async def delete_category(
    category_id: UUID,
    spending_repo: SpendingRepository = Depends(get_spending_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    async with uow:
        success = await spending_repo.delete_category(category_id)

    if not success:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    return StandardResponse(message="Categoria deletada com sucesso")
