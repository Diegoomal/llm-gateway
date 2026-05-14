from collections import defaultdict

from adapters.observability.prometheus_renderer import (
    metric_labels,
    new_histogram,
    observe_histogram,
    render_histogram,
)
from domain.llm_response import TokenUsage


class InMemoryMetricsRecorder:
    def __init__(self):
        self.requests_total = defaultdict(int)
        self.duration_seconds = defaultdict(float)
        self.request_duration_histogram = new_histogram()
        self.provider_errors_total = defaultdict(int)
        self.tokens_total = defaultdict(int)
        self.tokens_per_second = defaultdict(float)
        self.active_requests = defaultdict(int)
        self.fallbacks_total = defaultdict(int)
        self.idempotency_total = defaultdict(int)
        self.first_token_latency_seconds = defaultdict(float)
        self.first_token_latency_histogram = new_histogram()
        self.generation_duration_seconds = defaultdict(float)
        self.generation_duration_histogram = new_histogram()
        self.cold_start_detected_total = defaultdict(int)

    def increment_active_requests(self, provider: str, model: str) -> None:
        self.active_requests[(provider, model)] += 1

    def decrement_active_requests(self, provider: str, model: str) -> None:
        key = (provider, model)
        self.active_requests[key] = max(0, self.active_requests[key] - 1)

    def record_request(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
        duration_seconds: float,
        usage: TokenUsage,
    ) -> None:
        labels = (provider, model, status, endpoint)
        self.requests_total[labels] += 1
        self.duration_seconds[labels] += duration_seconds
        observe_histogram(
            self.request_duration_histogram,
            labels,
            duration_seconds,
        )
        self.tokens_total[(provider, model, status, endpoint)] += (
            usage.total_tokens
        )
        if duration_seconds > 0 and usage.total_tokens > 0:
            self.tokens_per_second[labels] = (
                usage.total_tokens / duration_seconds
            )

    def record_provider_error(
        self,
        provider: str,
        model: str,
        endpoint: str,
    ) -> None:
        self.provider_errors_total[(provider, model, endpoint)] += 1

    def record_fallback(
        self,
        from_provider: str,
        from_model: str,
        to_provider: str,
        to_model: str,
        status: str,
    ) -> None:
        self.fallbacks_total[
            (from_provider, from_model, to_provider, to_model, status)
        ] += 1

    def record_idempotency_event(self, endpoint: str, status: str) -> None:
        self.idempotency_total[(endpoint, status)] += 1

    def record_generation_timing(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
        first_token_latency_seconds: float | None = None,
        generation_duration_seconds: float | None = None,
    ) -> None:
        labels = (provider, model, status, endpoint)
        if first_token_latency_seconds is not None:
            self.first_token_latency_seconds[labels] += (
                first_token_latency_seconds
            )
            observe_histogram(
                self.first_token_latency_histogram,
                labels,
                first_token_latency_seconds,
            )
        if generation_duration_seconds is not None:
            self.generation_duration_seconds[labels] += (
                generation_duration_seconds
            )
            observe_histogram(
                self.generation_duration_histogram,
                labels,
                generation_duration_seconds,
            )

    def record_cold_start_detected(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
    ) -> None:
        self.cold_start_detected_total[(provider, model, status, endpoint)] += 1

    def render_prometheus(self) -> str:
        lines = []

        for labels, value in sorted(self.requests_total.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_requests_total"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )

        for labels, value in sorted(self.duration_seconds.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_request_duration_seconds"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )
        render_histogram(
            lines,
            "llm_request_duration_seconds",
            self.request_duration_histogram,
        )

        for labels, value in sorted(self.provider_errors_total.items()):
            provider, model, endpoint = labels
            lines.append(
                "llm_provider_errors_total"
                f'{metric_labels(provider, model, "error", endpoint)} {value}'
            )

        for labels, value in sorted(self.tokens_total.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_tokens_total"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )

        for labels, value in sorted(self.tokens_per_second.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_tokens_per_second"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )

        for labels, value in sorted(self.active_requests.items()):
            provider, model = labels
            lines.append(
                "llm_active_requests"
                f'{{provider="{provider}",model="{model}"}} {value}'
            )

        for labels, value in sorted(self.fallbacks_total.items()):
            from_provider, from_model, to_provider, to_model, status = labels
            lines.append(
                "llm_fallbacks_total"
                "{"
                f'from_provider="{from_provider}",'
                f'from_model="{from_model}",'
                f'to_provider="{to_provider}",'
                f'to_model="{to_model}",'
                f'status="{status}"'
                f"}} {value}"
            )

        for labels, value in sorted(self.idempotency_total.items()):
            endpoint, status = labels
            lines.append(
                "llm_idempotency_total"
                f'{{endpoint="{endpoint}",status="{status}"}} {value}'
            )

        for labels, value in sorted(self.first_token_latency_seconds.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_first_token_latency_seconds"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )
        render_histogram(
            lines,
            "llm_first_token_latency_seconds",
            self.first_token_latency_histogram,
        )

        for labels, value in sorted(self.generation_duration_seconds.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_generation_duration_seconds"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )
        render_histogram(
            lines,
            "llm_generation_duration_seconds",
            self.generation_duration_histogram,
        )

        for labels, value in sorted(self.cold_start_detected_total.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_cold_start_detected_total"
                f'{metric_labels(provider, model, status, endpoint)} {value}'
            )

        return "\n".join(lines) + "\n"
