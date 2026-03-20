import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from src.infra.config import settings
from src.api.main import app

@pytest.mark.asyncio
async def test_evolution_webhook_queued():
    payload = {
        "event": "messages.upsert",
        "instance": settings.evolution_instance,
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "id": "ABC"},
            "message": {"conversation": "Teste de integração"},
            "messageType": "conversation"
        }
    }
    
    with patch("src.api.routers.webhook.background_process_message", new_callable=AsyncMock) as mock_bg:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/webhook/evolution", json=payload)
            
        assert response.status_code == 200
        assert response.json() == {"status": "queued"}
        mock_bg.assert_called_once()

@pytest.mark.asyncio
async def test_simulate_message_endpoint():
    payload = {"phone": "5511999999999", "text": "Simulação"}
    
    with patch("src.api.routers.webhook.background_process_message", new_callable=AsyncMock) as mock_bg:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/webhook/dev/simulate-message", json=payload)
            
        assert response.status_code == 200
        mock_bg.assert_called_once()
