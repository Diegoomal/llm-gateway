from dataclasses import dataclass, field

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse


RequestRecord = tuple[LLMRequest, LLMResponse]


@dataclass(frozen=True)
class RequestHistoryFilters:
    provider: str | None = None
    model: str | None = None
    status: str | None = None
    endpoint: str | None = None


@dataclass(frozen=True)
class RequestHistoryPage:
    items: list[RequestRecord] = field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
