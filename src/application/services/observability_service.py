import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from application.ports.metrics_recorder import MetricsRecorder
from domain.llm_response import LLMResponse
from domain.model_route import ModelRoute


logger = logging.getLogger("llm_gateway")


@dataclass(frozen=True)
class RequestTimer:
    started_at: float

    @property
    def duration_seconds(self) -> float:
        return time.perf_counter() - self.started_at


class ObservabilityService:
    def __init__(self, metrics_recorder: MetricsRecorder):
        self.metrics_recorder = metrics_recorder

    @contextmanager
    def track_active_request(self, route: ModelRoute) -> Iterator[RequestTimer]:
        self.metrics_recorder.increment_active_requests(
            route.provider.value,
            route.model,
        )
        timer = RequestTimer(started_at=time.perf_counter())
        try:
            yield timer
        finally:
            self.metrics_recorder.decrement_active_requests(
                route.provider.value,
                route.model,
            )

    def record(
        self,
        response: LLMResponse,
        endpoint: str,
        duration_seconds: float,
    ) -> None:
        self.metrics_recorder.record_request(
            provider=response.provider.value,
            model=response.model,
            endpoint=endpoint,
            status=response.status,
            duration_seconds=duration_seconds,
            usage=response.usage,
        )

        if response.error:
            self.metrics_recorder.record_provider_error(
                provider=response.provider.value,
                model=response.model,
                endpoint=endpoint,
            )

        logger.info(
            json.dumps(
                {
                    "request_id": response.request_id,
                    "provider": response.provider.value,
                    "model": response.model,
                    "endpoint": endpoint,
                    "status": response.status,
                    "latency_ms": round(duration_seconds * 1000),
                    "error": response.error,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            )
        )
