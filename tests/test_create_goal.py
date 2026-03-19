import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from uuid import uuid4
from datetime import date

from src.use_cases.create_goal import CreateGoal

@pytest.mark.asyncio
async def test_create_goal_success():
    # Arrange
    mock_uow = AsyncMock()
    mock_repo = AsyncMock()
    client_id = uuid4()
    
    use_case = CreateGoal(mock_repo, mock_uow)
    
    # Act
    await use_case.execute(
        client_id=client_id,
        title="Viagem Japão",
        target_amount=Decimal("15000.00"),
        deadline=date(2027, 1, 1)
    )
    
    # Assert
    mock_repo.create.assert_called_once()
    mock_uow.__aenter__.assert_called_once()
    
    created_goal = mock_repo.create.call_args[0][0]
    assert created_goal.title == "Viagem Japão"
    assert created_goal.target_amount == Decimal("15000.00")
    assert created_goal.client_id == client_id
