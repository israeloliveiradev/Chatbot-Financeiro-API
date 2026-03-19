import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from src.use_cases.cancel_goal import CancelGoal

@pytest.mark.asyncio
async def test_cancel_goal_success():
    # Arrange
    mock_uow = AsyncMock()
    mock_repo = AsyncMock()
    goal_id = uuid4()
    
    mock_goal = MagicMock()
    mock_repo.get_by_id.return_value = mock_goal
    
    use_case = CancelGoal(mock_repo, mock_uow)
    
    # Act
    await use_case.execute(goal_id)
    
    # Assert
    assert mock_goal.status == "CANCELED"
    mock_repo.save.assert_called_once()
    mock_uow.__aenter__.assert_called_once()
