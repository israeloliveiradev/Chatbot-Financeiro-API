import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from src.domain.services.proactive_alerter import ProactiveAlerter
from src.infra.database.models import MonthlyGoalModel

@pytest.mark.asyncio
async def test_proactive_alerter_100_percent(mock_spending_repo, mock_evolution_client):
    alerter = ProactiveAlerter(mock_spending_repo, mock_evolution_client)
    
    client_id = uuid4()
    category_id = uuid4()
    
    # Mock meta de 100 reais
    goal = MagicMock(limit_amount=Decimal("100"), alert_100_sent=False, alert_80_sent=False)
    mock_spending_repo.get_monthly_goal.return_value = goal
    
    # Mock gasto de 120 reais
    mock_spending_repo.get_spendings_by_client_and_month.return_value = [
        MagicMock(amount=Decimal("120"), category_id=category_id)
    ]
    
    await alerter.check_spending_alerts(client_id, "5511...", category_id)
    
    # Verify
    mock_evolution_client.send_text_message.assert_called()
    assert "ALERTA DE LIMITE EXCEDIDO" in mock_evolution_client.send_text_message.call_args[0][1]
    assert goal.alert_100_sent is True

@pytest.mark.asyncio
async def test_proactive_alerter_no_duplicate(mock_spending_repo, mock_evolution_client):
    alerter = ProactiveAlerter(mock_spending_repo, mock_evolution_client)
    
    client_id = uuid4()
    category_id = uuid4()
    
    # Alerta já enviado
    goal = MagicMock(limit_amount=Decimal("100"), alert_100_sent=True)
    mock_spending_repo.get_monthly_goal.return_value = goal
    
    await alerter.check_spending_alerts(client_id, "5511...", category_id)
    
    # Verify: Não deve enviar novamente
    mock_evolution_client.send_text_message.assert_not_called()
