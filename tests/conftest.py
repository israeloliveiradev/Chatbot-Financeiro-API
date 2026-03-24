import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime

@pytest.fixture
def mock_uow():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.session = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.flush = AsyncMock()
    return uow

@pytest.fixture
def mock_client_repo():
    return AsyncMock()

@pytest.fixture
def mock_goal_repo():
    return AsyncMock()

@pytest.fixture
def mock_spending_repo():
    return AsyncMock()

@pytest.fixture
def mock_contribution_repo():
    return AsyncMock()

@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    # Mock padrão de análise de mensagem (conversa)
    client.analyze_message.return_value = '{"intent": "conversa", "reply_text": "Olá!", "extracted_data": {}}'
    client.generate_response.return_value = {"reply_text": "Insight da IA"}
    client.transcribe_audio.return_value = "Transcrição de teste"
    return client

@pytest.fixture
def mock_evolution_client():
    client = AsyncMock()
    client.send_text_message.return_value = {"status": "success"}
    client.send_presence.return_value = {"status": "success"}
    client.send_buttons.return_value = {"status": "success"}
    client.send_document.return_value = {"status": "success"}
    client.download_media.return_value = b"fake audio data"
    return client

@pytest.fixture
def mock_prompt_builder():
    builder = MagicMock()
    builder.build_system_prompt.return_value = "System Prompt"
    return builder

# Mocks para Use Cases (Injetados no ProcessMessage)
@pytest.fixture
def mock_get_client_case():
    return AsyncMock()

@pytest.fixture
def mock_get_goals_case():
    return AsyncMock()

@pytest.fixture
def mock_get_monthly_spending_case():
    return AsyncMock()

@pytest.fixture
def mock_register_spending_case():
    return AsyncMock()

@pytest.fixture
def mock_create_goal_case():
    return AsyncMock()

@pytest.fixture
def mock_register_contribution_case():
    return AsyncMock()

@pytest.fixture
def mock_proactive_alerter():
    return AsyncMock()
