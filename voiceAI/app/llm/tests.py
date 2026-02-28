import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.llm.services import LLMService


@pytest.mark.asyncio
async def test_query_from_text_no_api_key(monkeypatch):
    monkeypatch.setattr(LLMService, "API_KEY", None)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not set"):
        await LLMService.query_from_text_async("hello")


@pytest.mark.asyncio
async def test_query_from_text_success(monkeypatch):
    monkeypatch.setattr(LLMService, "API_KEY", "fake-key")

    request = httpx.Request("POST", LLMService.ENDPOINT)

    response = httpx.Response(
        200,
        request=request,
        json={"choices": [{"message": {"content": "Hello back!"}}]},
    )

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=response)

        result = await LLMService.query_from_text_async("Hello")

    assert result == "Hello back!"


@pytest.mark.asyncio
async def test_query_from_text_http_error(monkeypatch):
    monkeypatch.setattr(LLMService, "API_KEY", "fake-key")

    request = httpx.Request("POST", LLMService.ENDPOINT)
    response = httpx.Response(500, request=request)

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=response)

        result = await LLMService.query_from_text_async("Hello")

    assert result == "HTTP Error 500"


@pytest.mark.asyncio
async def test_query_from_text_request_error(monkeypatch):
    monkeypatch.setattr(LLMService, "API_KEY", "fake-key")

    mock_post = AsyncMock(side_effect=httpx.RequestError("Connection error"))

    with patch("httpx.AsyncClient.post", mock_post):
        result = await LLMService.query_from_text_async("Hello")

    assert result is None


@pytest.mark.asyncio
async def test_query_from_text_unexpected_error(monkeypatch):
    monkeypatch.setattr(LLMService, "API_KEY", "fake-key")

    mock_post = AsyncMock(side_effect=Exception("Something broke"))

    with patch("httpx.AsyncClient.post", mock_post):
        result = await LLMService.query_from_text_async("Hello")

    assert result is None
