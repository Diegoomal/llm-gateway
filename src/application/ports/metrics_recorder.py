from typing import Protocol

from domain.llm_response import TokenUsage


class MetricsRecorder(Protocol):
    def increment_active_requests(self, provider: str, model: str) -> None:
        pass

    def decrement_active_requests(self, provider: str, model: str) -> None:
        pass

    def record_request(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
        duration_seconds: float,
        usage: TokenUsage,
    ) -> None:
        pass

    def record_provider_error(
        self,
        provider: str,
        model: str,
        endpoint: str,
    ) -> None:
        pass
