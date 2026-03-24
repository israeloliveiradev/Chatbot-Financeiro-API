import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from uuid import uuid4
from datetime import date

from src.use_cases.register_spending import RegisterSpending
from src.domain.entities.spending import Spending

@pytest.mark.asyncio
async def test_register_spending_success():
    # Arrange
    mock_repo = AsyncMock()
    # Simula a categoria 'Alimentação' existente
    mock_category = MagicMock()
    mock_category.id = uuid4()
    mock_category.name = "Alimentação"
    mock_repo.get_category_by_name.return_value = mock_category
    
    client_id = uuid4()
    use_case = RegisterSpending(mock_repo)
    
    # Act
    result = await use_case.execute(
        client_id=client_id,
        category_name="Alimentação",
        amount=Decimal("50.00"),
        description="Almoço"
    )
    
    # Assert
    mock_repo.create_spending.assert_called_once()
    assert mock_repo.get_category_by_name.called
    # Verifica se os dados passados para o repo estão corretos
    created_spending = mock_repo.create_spending.call_args[0][0]
    assert created_spending.amount == Decimal("50.00")
    assert created_spending.client_id == client_id

@pytest.mark.asyncio
async def test_register_spending_category_not_found_fallback():
    # Arrange
    mock_repo = AsyncMock()
    # Primeira chamada: categoria específica não encontrada (None)
    # Segunda chamada: 'Outros' (fallback) encontrada
    mock_outros = MagicMock()
    mock_outros.id = uuid4()
    mock_repo.get_category_by_name.side_effect = [None, mock_outros]
    
    use_case = RegisterSpending(mock_repo)
    
    # Act
    await use_case.execute(uuid4(), "Desconhecida", Decimal("10.00"))
    
    # Assert
    assert mock_repo.get_category_by_name.call_count == 2
    mock_repo.create_spending.assert_called_once()
