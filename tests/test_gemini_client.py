import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.adapters.llm.gemini_client import GeminiClient

@pytest.mark.asyncio
async def test_gemini_analyze_message_success():
    mock_prompt_builder = MagicMock()
    client = GeminiClient(mock_prompt_builder)
    
    # Mock do objeto retornado pelo SDK do Google
    mock_response = MagicMock()
    mock_response.text = '{"intent": "conversa", "reply_text": "Olá"}'
    
    with patch.object(client.client.aio.models, "generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        
        result = await client.analyze_message("User prompt")
        
        assert "conversa" in result
        mock_gen.assert_called_once()

@pytest.mark.asyncio
async def test_gemini_generate_response():
    mock_prompt_builder = MagicMock()
    client = GeminiClient(mock_prompt_builder)
    
    mock_response = MagicMock()
    mock_response.text = "Insight da IA"
    
    with patch.object(client.client.aio.models, "generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        
        result = await client.generate_response("Conteúdo")
        
        assert result["reply_text"] == "Insight da IA"
