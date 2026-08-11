import asyncio
import time
from enum import Enum

import httpx

from app.common.logger import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the breaker is OPEN."""


def _is_provider_outage(exc: BaseException) -> bool:
    """Return True only for errors that indicate the provider itself is down.

    Transport failures and ``5xx`` responses count; ``4xx`` (auth, bad request,
    rate-limit handling is the caller's concern) and everything else do not.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.RequestError)


class AsyncCircuitBreaker:
    def __init__(
        self,
        *,
        fail_max: int = 5,
        reset_timeout: float = 30.0,
        name: str = "llm",
    ):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.name = name

        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, func, *args, **kwargs):
        """Run ``await func(*args, **kwargs)`` under the breaker's protection."""
        await self._before_call()
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            if _is_provider_outage(exc):
                await self._on_outage()
            else:
                # Provider responded (or a non-transport error): treat as a
                # healthy signal for the breaker, but surface the error.
                await self._on_success()
            raise
        else:
            await self._on_success()
            return result

    async def _before_call(self) -> None:
        async with self._lock:
            if self._state is not CircuitState.OPEN:
                return
            if time.monotonic() - self._opened_at >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker '%s' entering HALF_OPEN (trial)", self.name)
                return
            raise CircuitBreakerOpen(
                f"Circuit breaker '{self.name}' is open; provider calls are paused"
            )

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state is not CircuitState.CLOSED or self._failures:
                logger.info("Circuit breaker '%s' reset to CLOSED", self.name)
            self._failures = 0
            self._state = CircuitState.CLOSED

    async def _on_outage(self) -> None:
        async with self._lock:
            self._failures += 1
            if (
                self._state is CircuitState.HALF_OPEN
                or self._failures >= self.fail_max
            ):
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker '%s' OPEN after %d failure(s); "
                    "pausing provider calls for %.0fs",
                    self.name,
                    self._failures,
                    self.reset_timeout,
                )

    async def reset(self) -> None:
        """Force the breaker back to a clean CLOSED state."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._opened_at = 0.0
