import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


@dataclass
class ResilienceService:
    retry_attempts: int = 1
    retry_base_delay_ms: int = 100
    circuit_breaker_failure_threshold: int = 0
    circuit_breaker_recovery_seconds: int = 30
    _circuits: dict[tuple[str, str], CircuitState] = field(
        default_factory=dict,
    )

    async def execute(
        self,
        provider: str,
        model: str,
        call: Callable[[], Awaitable[T]],
    ) -> T:
        key = (provider, model)
        self._raise_if_open(key)
        attempts = max(1, self.retry_attempts)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                result = await call()
                self._record_success(key)
                return result
            except Exception as error:
                last_error = error
                if attempt == attempts - 1 or not self._is_transient(error):
                    self._record_failure(key)
                    raise
                delay = self.retry_base_delay_ms * (2**attempt) / 1000
                await asyncio.sleep(delay)

        raise last_error or RuntimeError("provider call failed")

    def _raise_if_open(self, key: tuple[str, str]) -> None:
        state = self._circuits.get(key)
        if state is None or state.opened_at is None:
            return
        elapsed = time.monotonic() - state.opened_at
        if elapsed < self.circuit_breaker_recovery_seconds:
            provider, model = key
            raise RuntimeError(
                f"circuit breaker open for provider={provider} model={model}"
            )
        state.opened_at = None

    def _record_success(self, key: tuple[str, str]) -> None:
        self._circuits[key] = CircuitState()

    def _record_failure(self, key: tuple[str, str]) -> None:
        if self.circuit_breaker_failure_threshold <= 0:
            return
        state = self._circuits.setdefault(key, CircuitState())
        state.failures += 1
        if state.failures >= self.circuit_breaker_failure_threshold:
            state.opened_at = time.monotonic()

    def _is_transient(self, error: Exception) -> bool:
        name = error.__class__.__name__.lower()
        message = str(error).lower()
        transient_markers = (
            "timeout",
            "connect",
            "429",
            "500",
            "502",
            "503",
            "504",
            "temporarily",
        )
        return any(
            marker in name or marker in message
            for marker in transient_markers
        )
