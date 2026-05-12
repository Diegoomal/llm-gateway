from collections import defaultdict

from domain.llm_response import TokenUsage


class InMemoryMetricsRecorder:
    def __init__(self):
        self.requests_total = defaultdict(int)
        self.duration_seconds = defaultdict(float)
        self.provider_errors_total = defaultdict(int)
        self.tokens_total = defaultdict(int)
        self.active_requests = defaultdict(int)

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
        self.tokens_total[(provider, model, status, endpoint)] += (
            usage.total_tokens
        )

    def record_provider_error(
        self,
        provider: str,
        model: str,
        endpoint: str,
    ) -> None:
        self.provider_errors_total[(provider, model, endpoint)] += 1

    def render_prometheus(self) -> str:
        lines = []

        for labels, value in sorted(self.requests_total.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_requests_total"
                f'{self._labels(provider, model, status, endpoint)} {value}'
            )

        for labels, value in sorted(self.duration_seconds.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_request_duration_seconds"
                f'{self._labels(provider, model, status, endpoint)} {value}'
            )

        for labels, value in sorted(self.provider_errors_total.items()):
            provider, model, endpoint = labels
            lines.append(
                "llm_provider_errors_total"
                f'{self._labels(provider, model, "error", endpoint)} {value}'
            )

        for labels, value in sorted(self.tokens_total.items()):
            provider, model, status, endpoint = labels
            lines.append(
                "llm_tokens_total"
                f'{self._labels(provider, model, status, endpoint)} {value}'
            )

        for labels, value in sorted(self.active_requests.items()):
            provider, model = labels
            lines.append(
                "llm_active_requests"
                f'{{provider="{provider}",model="{model}"}} {value}'
            )

        return "\n".join(lines) + "\n"

    def _labels(
        self,
        provider: str,
        model: str,
        status: str,
        endpoint: str,
    ) -> str:
        return (
            f'{{provider="{provider}",model="{model}",'
            f'status="{status}",endpoint="{endpoint}"}}'
        )
