import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from uuid import uuid4
from datetime import date

from src.use_cases.get_monthly_spending import GetMonthlySpending

@pytest.mark.asyncio
async def test_get_monthly_spending_calculates_correctly():
    # Arrange
    mock_repo = AsyncMock()
    client_id = uuid4()
    cat_id = uuid4()
    
    # Mock Categorias
    mock_category = MagicMock()
    mock_category.id = cat_id
    mock_category.name = "Transporte"
    mock_repo.get_all_categories.return_value = [mock_category]
    
    # Mock Metas Mensais
    mock_goal = MagicMock()
    mock_goal.category_id = cat_id
    mock_goal.limit_amount = Decimal("1000.00")
    mock_repo.get_monthly_goals_by_client_and_month.return_value = [mock_goal]
    
    # Mock Gastos
    mock_spending = MagicMock()
    mock_spending.category_id = cat_id
    mock_spending.amount = Decimal("350.00")
    mock_repo.get_spendings_by_client_and_month.return_value = [mock_spending]
    
    use_case = GetMonthlySpending(mock_repo)
    
    # Act
    summary = await use_case.execute(client_id, date(2026, 3, 19))
    
    # Assert
    assert isinstance(summary, list)
    assert len(summary) == 1
    item = summary[0]
    assert item["category"] == "Transporte"
    assert item["total_spent"] == 350.0
    assert item["available"] == 650.0
    assert item["percentage_used"] == 35.0
