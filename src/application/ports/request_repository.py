from typing import Protocol

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse
from domain.request_history import RequestHistoryFilters, RequestHistoryPage


class RequestRepository(Protocol):
    def save(self, request: LLMRequest, response: LLMResponse) -> None:
        pass

    def find_all(self) -> list[tuple[LLMRequest, LLMResponse]]:
        pass

    def find_page(
        self,
        limit: int,
        offset: int,
        filters: RequestHistoryFilters | None = None,
    ) -> RequestHistoryPage:
        pass

    def find_by_request_id(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        pass

    def find_by_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        pass

    def find_cache_entry(
        self,
        cache_key: str,
    ) -> LLMResponse | None:
        pass
