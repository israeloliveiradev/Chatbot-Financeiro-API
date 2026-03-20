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
    mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
    mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
):
    # Setup
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_client_repo.get_by_phone.return_value = client
    
    # Mock use cases returning empty
    with patch("src.use_cases.process_message.GetGoals") as MockGetGoals, \
         patch("src.use_cases.process_message.GetMonthlySpending") as MockGetMonthly:
        
        MockGetGoals.return_value.execute = AsyncMock(return_value=[])
        MockGetMonthly.return_value.execute = AsyncMock(return_value=[])

        use_case = ProcessMessage(
            mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
            mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
        )

        await use_case.execute(phone, "Oi")

        # Verify
        mock_evolution_client.send_text_message.assert_called_with(phone, "Olá!")

@pytest.mark.asyncio
async def test_process_registrar_gasto(
    mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
    mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_client_repo.get_by_phone.return_value = client
    
    # Mock Gemini returning registrar_gasto
    mock_gemini_client.analyze_message.return_value = json.dumps({
        "intent": "registrar_gasto",
        "extracted_data": {"category_name": "Alimentação", "amount": 50, "description": "Almoço"},
        "reply_text": "Gasto registrado!"
    })

    # Mock Repos and Services
    mock_spending_repo.get_all_categories.return_value = [MagicMock(id=uuid4(), name="Alimentação")]
    
    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
        mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
    )

    with patch.object(use_case.alerter, "check_spending_alerts") as mock_alert_call:
        await use_case.execute(phone, "Gastei 50 com almoço")
        
        # Verify
        mock_spending_repo.create_spending.assert_called()
        mock_alert_call.assert_called()
        mock_evolution_client.send_buttons.assert_called()

@pytest.mark.asyncio
async def test_process_criar_objetivo(
    mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
    mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_client_repo.get_by_phone.return_value = client
    
    mock_gemini_client.analyze_message.return_value = json.dumps({
        "intent": "criar_objetivo",
        "extracted_data": {"title": "Carro Novo", "target_amount": 50000, "deadline": "2026-12-31"},
        "reply_text": "Objetivo em processamento..."
    })

    use_case = ProcessMessage(
        mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
        mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
    )

    await use_case.execute(phone, "Quero economizar 50k para um carro")
    
    # Verify
    mock_goal_repo.create.assert_called()
    mock_evolution_client.send_buttons.assert_called()

@pytest.mark.asyncio
async def test_process_listar_objetivos(
    mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
    mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_client_repo.get_by_phone.return_value = client
    
    mock_gemini_client.analyze_message.return_value = json.dumps({
        "intent": "listar_objetivos",
        "extracted_data": {},
        "reply_text": ""
    })

    # Mock GetGoals use case
    with patch("src.use_cases.process_message.GetGoals") as MockGetGoals:
        MockGetGoals.return_value.execute = AsyncMock(return_value=[
            MagicMock(title="Carro", target_amount=Decimal("50000"), current_amount=Decimal("1000"))
        ])

        use_case = ProcessMessage(
            mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
            mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
        )

        await use_case.execute(phone, "Quais meus objetivos?")
        
        # Verify
        mock_evolution_client.send_buttons.assert_called()
        # Verificar se chamou o cálculo da reserva (implícito na resposta)

@pytest.mark.asyncio
async def test_process_simular_compra(
    mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
    mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
):
    phone = "5511999999999"
    client = Client(id=uuid4(), phone=phone, name="Test User", monthly_income=Decimal("5000"))
    mock_client_repo.get_by_phone.return_value = client
    
    # Simulação: item de 1000, disponível 2000
    mock_gemini_client.analyze_message.return_value = json.dumps({
        "intent": "simular_compra",
        "extracted_data": {"item": "Fone", "amount": 1000},
        "reply_text": "Analisando..."
    })

    summary = [{"limit_amount": 5000, "total_spent": 3000}] # Disponível 2000

    with patch("src.use_cases.process_message.GetMonthlySpending") as MockGetMonthly:
        MockGetMonthly.return_value.execute = AsyncMock(return_value=summary)

        use_case = ProcessMessage(
            mock_uow, mock_client_repo, mock_goal_repo, mock_spending_repo,
            mock_gemini_client, mock_evolution_client, mock_prompt_builder, mock_contribution_repo
        )

        await use_case.execute(phone, "Posso comprar um fone de 1000?")
        
        # Verify
        mock_evolution_client.send_buttons.assert_called()
