import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from uuid import uuid4
from src.use_cases.register_contribution import RegisterContribution

@pytest.mark.asyncio
async def test_register_contribution_success():
    # Arrange
    mock_uow = AsyncMock()
    mock_repo = AsyncMock()
    goal_id = uuid4()
    
    # Mock do Objetivo
    mock_goal = MagicMock()
    mock_goal.id = goal_id
    mock_goal.current_amount = Decimal("100.00")
    mock_repo.get_by_id.return_value = mock_goal
    
    use_case = RegisterContribution(mock_repo, mock_uow)
    
    # Act
    await use_case.execute(goal_id, Decimal("50.00"))
    
    # Assert
    mock_repo.save.assert_called_once()
    assert mock_goal.current_amount == Decimal("150.00")
    mock_uow.__aenter__.assert_called_once()
