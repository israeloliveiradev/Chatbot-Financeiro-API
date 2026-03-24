import pytest
import json
from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import AsyncMock, patch, MagicMock
from src.use_cases.process_message import ProcessMessage
from src.domain.entities.client import Client

@pytest.mark.asyncio
async def test_process_conversa(
    mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
    mock_proactive_alerter,
    mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
    mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
):
    # Setup
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_get_client_case.execute = AsyncMock(return_value=client)
    mock_get_goals_case.execute = AsyncMock(return_value=[])
    mock_get_monthly_spending_case.execute = AsyncMock(return_value=[])
    
    # Mock LLM returning a simple conversation
    mock_llm_client.analyze_message.return_value = json.dumps({
        "intent": "conversa",
        "reply_text": "Olá! Como posso ajudar?",
        "extracted_data": {}
    })

    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
        mock_proactive_alerter,
        mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
        mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
    )

    await use_case.execute(phone, "Oi")

    # Verify
    mock_evolution_client.send_text_message.assert_called_with(phone, "Olá! Como posso ajudar?")

@pytest.mark.asyncio
async def test_process_registrar_gasto(
    mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
    mock_proactive_alerter,
    mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
    mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_get_client_case.execute = AsyncMock(return_value=client)
    mock_get_goals_case.execute = AsyncMock(return_value=[])
    mock_get_monthly_spending_case.execute = AsyncMock(return_value=[])
    
    # Mock LLM returning registrar_gasto
    mock_llm_client.analyze_message.return_value = json.dumps({
        "intent": "registrar_gasto",
        "extracted_data": {"category": "Alimentação", "amount": 50, "description": "Almoço"},
        "reply_text": "Gasto registrado!"
    })

    # Mock register_spending_case returning a spending with a category_id
    fake_spending = MagicMock()
    fake_spending.category_id = uuid4()
    mock_register_spending_case.execute = AsyncMock(return_value=fake_spending)

    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
        mock_proactive_alerter,
        mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
        mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
    )

    await use_case.execute(phone, "Gastei 50 com almoço")
    
    # Verify
    mock_register_spending_case.execute.assert_called_with(
        client.id, "Alimentação", Decimal("50"), "Almoço"
    )
    mock_proactive_alerter.check_spending_alerts.assert_called_with(
        client.id, phone, fake_spending.category_id
    )
    mock_evolution_client.send_text_message.assert_called()

@pytest.mark.asyncio
async def test_process_criar_objetivo(
    mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
    mock_proactive_alerter,
    mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
    mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_get_client_case.execute = AsyncMock(return_value=client)
    mock_get_goals_case.execute = AsyncMock(return_value=[])
    mock_get_monthly_spending_case.execute = AsyncMock(return_value=[])
    
    mock_llm_client.analyze_message.return_value = json.dumps({
        "intent": "criar_objetivo",
        "extracted_data": {"title": "Carro Novo", "target_amount": 50000, "deadline": "2026-12-31"},
        "reply_text": "Objetivo em processamento..."
    })

    mock_create_goal_case.execute = AsyncMock()

    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
        mock_proactive_alerter,
        mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
        mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
    )

    await use_case.execute(phone, "Quero economizar 50k para um carro")
    
    # Verify
    mock_create_goal_case.execute.assert_called_with(
        client.id, "Carro Novo", Decimal("50000"), date(2026, 12, 31)
    )
    mock_evolution_client.send_text_message.assert_called()

@pytest.mark.asyncio
async def test_process_listar_objetivos(
    mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
    mock_proactive_alerter,
    mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
    mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_get_client_case.execute = AsyncMock(return_value=client)
    
    mock_llm_client.analyze_message.return_value = json.dumps({
        "intent": "listar_objetivos",
        "extracted_data": {},
        "reply_text": ""
    })

    # Mock GetGoals result
    goals_list = [
        MagicMock(title="Carro", target_amount=Decimal("50000"), current_amount=Decimal("1000"), deadline=None)
    ]
    mock_get_goals_case.execute = AsyncMock(return_value=goals_list)
    mock_get_monthly_spending_case.execute = AsyncMock(return_value=[])

    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
        mock_proactive_alerter,
        mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
        mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
    )

    await use_case.execute(phone, "Quais meus objetivos?")
    
    # Verify
    assert mock_evolution_client.send_text_message.called
    msg = mock_evolution_client.send_text_message.call_args[0][1]
    assert "Carro" in msg
    assert "R$ 1000" in msg

@pytest.mark.asyncio
async def test_process_audio_flow(
    mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
    mock_proactive_alerter,
    mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
    mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_get_client_case.execute = AsyncMock(return_value=client)
    mock_get_goals_case.execute = AsyncMock(return_value=[])
    mock_get_monthly_spending_case.execute = AsyncMock(return_value=[])
    
    # Mock LLM transcribe
    mock_llm_client.transcribe_audio = AsyncMock(return_value="Gastei 100 reais")
    mock_llm_client.analyze_message.return_value = json.dumps({
        "intent": "registrar_gasto",
        "extracted_data": {"category": "Outros", "amount": 100},
        "reply_text": "Gasto de áudio registrado!"
    })

    mock_register_spending_case.execute = AsyncMock(return_value=None)

    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_llm_client, mock_evolution_client, mock_prompt_builder,
        mock_proactive_alerter,
        mock_get_client_case, mock_get_goals_case, mock_get_monthly_spending_case,
        mock_register_spending_case, mock_create_goal_case, mock_register_contribution_case
    )

    await use_case.execute(phone, "", is_audio=True, media_url="http://fake.url")
    
    # Verify
    mock_evolution_client.download_media.assert_called_with("http://fake.url")
    mock_llm_client.transcribe_audio.assert_called()
    mock_register_spending_case.execute.assert_called_with(client.id, "Outros", Decimal("100"), "")
