import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime

@pytest.fixture
def mock_uow():
    uow = MagicMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
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
def mock_gemini_client():
    client = AsyncMock()
    # Mock padrão de análise de mensagem (conversa)
    client.analyze_message.return_value = '{"intent": "conversa", "reply_text": "Olá!", "extracted_data": {}}'
    client.generate_response.return_value = {"reply_text": "Insight da IA"}
    return client

@pytest.fixture
def mock_evolution_client():
    client = AsyncMock()
    client.send_text_message.return_value = {"status": "success"}
    client.send_buttons.return_value = {"status": "success"}
    client.send_document.return_value = {"status": "success"}
    return client

@pytest.fixture
def mock_prompt_builder():
    builder = MagicMock()
    builder.build_system_prompt.return_value = "System Prompt"
    return builder
