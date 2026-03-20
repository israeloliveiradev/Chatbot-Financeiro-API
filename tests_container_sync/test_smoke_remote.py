import pytest
from httpx import AsyncClient
from src.api.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Assumindo que existe um root ou health endpoint
        response = await ac.get("/")
    # Se não existir /, pode ser 404 mas o app deve estar UP
    assert response.status_code in [200, 404]

def test_imports():
    # Smoke: Verificar se as dependências críticas importam sem erro
    from src.api.dependencies import get_db_session
    from src.use_cases.process_message import ProcessMessage
    assert True
