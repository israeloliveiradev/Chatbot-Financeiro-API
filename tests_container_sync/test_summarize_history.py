import pytest
from unittest.mock import AsyncMock, MagicMock
from src.use_cases.summarize_history import SummarizeHistory

@pytest.mark.asyncio
async def test_summarize_history_success():
    # Arrange
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = {"reply_text": "Resumo da conversa."}
    
    use_case = SummarizeHistory(mock_llm)
    history = [
        {"role": "user", "content": "Gastei 50 no almoço"},
        {"role": "assistant", "content": "Ok, registrado."}
    ]
    
    # Act
    summary = await use_case.execute(history)
    
    # Assert
    assert summary == "Resumo da conversa."
    mock_llm.generate_response.assert_called_once()
    assert "Gastei 50 no almoço" in mock_llm.generate_response.call_args[0][0]

@pytest.mark.asyncio
async def test_summarize_history_empty():
    mock_llm = AsyncMock()
    use_case = SummarizeHistory(mock_llm)
    
    summary = await use_case.execute([])
    
    assert summary == ""
    mock_llm.generate_response.assert_not_called()
