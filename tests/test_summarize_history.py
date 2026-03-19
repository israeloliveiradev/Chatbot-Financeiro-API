import pytest
from unittest.mock import AsyncMock, MagicMock
from src.use_cases.summarize_history import SummarizeHistory

@pytest.mark.asyncio
async def test_summarize_history_success():
    # Arrange
    mock_gemini = AsyncMock()
    mock_response = MagicMock()
    mock_response.text = "Resumo da conversa."
    mock_gemini.chat.return_value = mock_response
    
    use_case = SummarizeHistory(mock_gemini)
    history = [
        {"role": "user", "content": "Gastei 50 no almoço"},
        {"role": "assistant", "content": "Ok, registrado."}
    ]
    
    # Act
    summary = await use_case.execute(history)
    
    # Assert
    assert summary == "Resumo da conversa."
    mock_gemini.chat.assert_called_once()
    assert "Gastei 50 no almoço" in mock_gemini.chat.call_args[1]["message"]

@pytest.mark.asyncio
async def test_summarize_history_empty():
    mock_gemini = AsyncMock()
    use_case = SummarizeHistory(mock_gemini)
    
    summary = await use_case.execute([])
    
    assert summary == ""
    mock_gemini.chat.assert_not_called()
