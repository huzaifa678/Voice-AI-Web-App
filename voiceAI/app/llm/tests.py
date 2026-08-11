import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.llm.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from app.llm.services import LLMService, llm_circuit_breaker

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


@pytest.fixture(autouse=True)
async def _reset_breaker():
    """Keep the shared LLM breaker from leaking state between tests."""
    await llm_circuit_breaker.reset()
    yield
    await llm_circuit_breaker.reset()


@pytest.mark.asyncio
async def test_query_from_text_no_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="API key is not set"):
        await LLMService.query_from_text_async("hello")


@pytest.mark.asyncio
async def test_query_from_text_success(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    request = httpx.Request("POST", ENDPOINT)
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
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    request = httpx.Request("POST", ENDPOINT)
    response = httpx.Response(500, request=request)

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(return_value=response)

        result = await LLMService.query_from_text_async("Hello")

    assert result == "HTTP Error 500"


@pytest.mark.asyncio
async def test_query_from_text_request_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    with patch(
        "httpx.AsyncClient.post",
        AsyncMock(side_effect=httpx.RequestError("Connection error")),
    ):
        result = await LLMService.query_from_text_async("Hello")

    assert result == ""


@pytest.mark.asyncio
async def test_query_from_text_unexpected_error_propagates(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    with patch(
        "httpx.AsyncClient.post",
        AsyncMock(side_effect=Exception("Something broke")),
    ):
        with pytest.raises(Exception, match="Something broke"):
            await LLMService.query_from_text_async("Hello")


def _outage():
    return httpx.ConnectError("connection refused")


def _http_error(status):
    request = httpx.Request("POST", ENDPOINT)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


@pytest.mark.asyncio
async def test_breaker_opens_after_fail_max_outages():
    breaker = AsyncCircuitBreaker(fail_max=3, reset_timeout=60)

    async def failing():
        raise _outage()

    for _ in range(3):
        with pytest.raises(httpx.RequestError):
            await breaker.call(failing)

    assert breaker.state is CircuitState.OPEN

    # Further calls short-circuit without invoking the provider at all.
    with pytest.raises(CircuitBreakerOpen):
        await breaker.call(failing)


@pytest.mark.asyncio
async def test_breaker_ignores_4xx_client_errors():
    breaker = AsyncCircuitBreaker(fail_max=2, reset_timeout=60)

    async def client_error():
        raise _http_error(404)

    for _ in range(5):
        with pytest.raises(httpx.HTTPStatusError):
            await breaker.call(client_error)

    # 4xx means the provider answered -> breaker stays closed.
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_breaker_trips_on_5xx():
    breaker = AsyncCircuitBreaker(fail_max=2, reset_timeout=60)

    async def server_error():
        raise _http_error(503)

    for _ in range(2):
        with pytest.raises(httpx.HTTPStatusError):
            await breaker.call(server_error)

    assert breaker.state is CircuitState.OPEN


@pytest.mark.asyncio
async def test_breaker_half_open_recovers_on_success():
    breaker = AsyncCircuitBreaker(fail_max=1, reset_timeout=0)  # reopen instantly eligible

    async def failing():
        raise _outage()

    async def ok():
        return "recovered"

    with pytest.raises(httpx.RequestError):
        await breaker.call(failing)
    assert breaker.state is CircuitState.OPEN

    # reset_timeout=0 -> next call is a HALF_OPEN trial; success closes it.
    assert await breaker.call(ok) == "recovered"
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_service_returns_empty_when_breaker_open(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    await llm_circuit_breaker.reset()
    llm_circuit_breaker._state = CircuitState.OPEN
    import time

    llm_circuit_breaker._opened_at = time.monotonic()

    with patch("httpx.AsyncClient.post") as mock_post:
        result = await LLMService.query_from_text_async("Hello")

    assert result == ""
    mock_post.assert_not_called()  # provider never contacted while open
