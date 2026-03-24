from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from decimal import Decimal
from datetime import date, datetime, timezone
from uuid import UUID
from src.api.dependencies import (
    get_client_repository,
    get_spending_repository,
    get_unit_of_work,
)
from src.domain.entities.monthly_goal import MonthlyGoal
from src.domain.entities.spending import Spending
from src.domain.entities.spending_category import SpendingCategory
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.spending_repository import SpendingRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.use_cases.get_monthly_spending import GetMonthlySpending
from src.api.schemas import (
    StandardResponse,
    SpendingSummaryResponse,
    TransactionCreateRequest,
    TransactionResponse,
    MonthlyGoalCreateRequest,
    MonthlyGoalResponse,
    CategoryCreateRequest,
    CategoryResponse,
)

router = APIRouter(prefix="/spending", tags=["Gestão de Gastos"])

async def _get_client_or_404(phone: str, client_repo: ClientRepository):
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client

# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", summary="Lista categorias", response_model=StandardResponse)
async def list_categories(
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    categories = await spending_repo.get_all_categories()
    data = [{"id": str(c.id), "name": c.name} for c in categories]
    return StandardResponse(data=data)

@router.post("/categories", summary="Criar categoria", status_code=201, response_model=StandardResponse)
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

# ── Transactions ──────────────────────────────────────────────────────────────

@router.post("/{phone}/transactions", summary="Registrar gasto", status_code=201, response_model=StandardResponse)
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
        raise HTTPException(status_code=404, detail=f"Categoria '{request.category_name}' não encontrada")

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

@router.post("/{phone}/transactions/batch", summary="Registrar gastos em lote", status_code=201, response_model=StandardResponse)
async def create_transactions_batch(
    phone: str,
    requests: List[TransactionCreateRequest],
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    client = await _get_client_or_404(phone, client_repo)
    
    results = []
    async with uow:
        for req in requests:
            category = await spending_repo.get_category_by_name(req.category_name)
            if not category:
                continue # Ou levantar erro se preferir falha total
                
            spent_at = req.spent_at or datetime.now(tz=timezone.utc)
            spending = Spending(
                client_id=client.id,
                category_id=category.id,
                amount=Decimal(str(req.amount)),
                description=req.description,
                spent_at=spent_at,
            )
            saved = await spending_repo.create_spending(spending)
            results.append(TransactionResponse(
                id=str(saved.id),
                category_id=str(saved.category_id),
                category_name=category.name,
                amount=float(saved.amount),
                description=saved.description,
                spent_at=saved.spent_at.isoformat(),
            ).model_dump())

    return StandardResponse(message=f"{len(results)} transações registradas", data=results)

@router.get("/{phone}/transactions", summary="Lista transações do mês", response_model=StandardResponse)
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

# ── Summary & Monthly Goals ───────────────────────────────────────────────────

@router.get("/{phone}/summary", summary="Resumo de gastos", response_model=StandardResponse)
async def list_spending_summary(
    phone: str,
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    summary = await GetMonthlySpending(spending_repo).execute(client.id, date.today())
    return StandardResponse(data=summary)

@router.post("/{phone}/monthly-goals", summary="Definir meta mensal", status_code=201, response_model=StandardResponse)
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
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    try:
        parsed = datetime.strptime(request.year_month, "%Y-%m").date().replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail="year_month deve ser YYYY-MM")

    existing = await spending_repo.get_monthly_goal(client.id, category.id, parsed)
    if existing:
        raise HTTPException(status_code=409, detail="Meta já existe")

    monthly_goal = MonthlyGoal(
        client_id=client.id,
        category_id=category.id,
        year_month=parsed,
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

@router.get("/{phone}/monthly-goals", summary="Listar metas mensais", response_model=StandardResponse)
async def list_monthly_goals(
    phone: str,
    year_month: Optional[str] = None, # Formato YYYY-MM
    client_repo: ClientRepository = Depends(get_client_repository),
    spending_repo: SpendingRepository = Depends(get_spending_repository),
):
    client = await _get_client_or_404(phone, client_repo)
    
    if year_month:
        try:
            parsed = datetime.strptime(year_month, "%Y-%m").date().replace(day=1)
        except ValueError:
            raise HTTPException(status_code=422, detail="year_month deve ser YYYY-MM")
    else:
        parsed = date.today().replace(day=1)

    goals = await spending_repo.get_monthly_goals_by_client_and_month(client.id, parsed)
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
