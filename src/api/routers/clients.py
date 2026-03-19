from fastapi import APIRouter, Depends, HTTPException
from src.api.dependencies import get_client_repository, get_unit_of_work
from src.domain.entities.client import Client
from src.domain.repositories.client_repository import ClientRepository
from src.domain.repositories.unit_of_work import UnitOfWork
from src.use_cases.get_client_by_phone import GetClientByPhone
from src.api.schemas import StandardResponse, ClientResponse, ClientCreateRequest
from decimal import Decimal

router = APIRouter(prefix="/clients", tags=["Clientes"])

async def _get_client_or_404(phone: str, client_repo: ClientRepository) -> Client:
    client = await GetClientByPhone(client_repo).execute(phone)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client

@router.get("/{phone}", summary="Busca cliente", response_model=StandardResponse)
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

@router.post("", summary="Criar cliente", status_code=201, response_model=StandardResponse)
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
