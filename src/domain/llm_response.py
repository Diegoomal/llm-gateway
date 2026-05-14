from dataclasses import dataclass, field
from typing import Any

from domain.provider_name import ProviderName


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    request_id: str
    provider: ProviderName
    model: str
    status: str
    content: str | None = None
    embeddings: list[list[float]] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None
    trace_id: str | None = None
    provider_status_code: int | None = None
    fallback_used: bool = False
    fallback_from_provider: ProviderName | None = None
    fallback_from_model: str | None = None
    latency_ms: int | None = None
    error_type: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == "success" and self.error is None


@dataclass(frozen=True)
class LLMStreamChunk:
    request_id: str
    provider: ProviderName
    model: str
    content_delta: str = ""
    finish_reason: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
