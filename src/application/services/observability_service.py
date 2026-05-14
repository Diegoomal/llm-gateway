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
    def __init__(
        self,
        metrics_recorder: MetricsRecorder,
        cold_start_first_token_threshold_seconds: float = 5,
    ):
        self.metrics_recorder = metrics_recorder
        self.cold_start_first_token_threshold_seconds = (
            cold_start_first_token_threshold_seconds
        )

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
        request_size: int = 0,
        response_size: int = 0,
        first_token_latency_seconds: float | None = None,
        generation_duration_seconds: float | None = None,
    ) -> None:
        self.metrics_recorder.record_request(
            provider=response.provider.value,
            model=response.model,
            endpoint=endpoint,
            status=response.status,
            duration_seconds=duration_seconds,
            usage=response.usage,
        )
        self.metrics_recorder.record_generation_timing(
            provider=response.provider.value,
            model=response.model,
            endpoint=endpoint,
            status=response.status,
            first_token_latency_seconds=first_token_latency_seconds,
            generation_duration_seconds=generation_duration_seconds,
        )
        if (
            first_token_latency_seconds is not None
            and first_token_latency_seconds
            >= self.cold_start_first_token_threshold_seconds
        ):
            self.metrics_recorder.record_cold_start_detected(
                provider=response.provider.value,
                model=response.model,
                endpoint=endpoint,
                status=response.status,
            )

        if response.error:
            self.metrics_recorder.record_provider_error(
                provider=response.provider.value,
                model=response.model,
                endpoint=endpoint,
            )

        if (
            response.fallback_used
            and response.fallback_from_provider
            and response.fallback_from_model
        ):
            self.metrics_recorder.record_fallback(
                from_provider=response.fallback_from_provider.value,
                from_model=response.fallback_from_model,
                to_provider=response.provider.value,
                to_model=response.model,
                status=response.status,
            )

        logger.info(
            json.dumps(
                {
                    "trace_id": response.trace_id,
                    "request_id": response.request_id,
                    "provider": response.provider.value,
                    "model": response.model,
                    "endpoint": endpoint,
                    "status": response.status,
                    "latency_ms": round(duration_seconds * 1000),
                    "error": response.error,
                    "provider_status_code": response.provider_status_code,
                    "fallback_used": response.fallback_used,
                    "request_size": request_size,
                    "response_size": response_size,
                    "first_token_latency_ms": (
                        round(first_token_latency_seconds * 1000)
                        if first_token_latency_seconds is not None
                        else None
                    ),
                    "generation_duration_ms": (
                        round(generation_duration_seconds * 1000)
                        if generation_duration_seconds is not None
                        else None
                    ),
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            )
        )
