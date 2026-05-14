from collections.abc import AsyncIterator
from typing import Protocol

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, LLMStreamChunk
from domain.idempotency import IdempotencyReservation
from domain.request_history import RequestHistoryFilters, RequestHistoryPage


class ForManagingLLMRequests(Protocol):
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        pass

    def stream_chat_completion(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[LLMStreamChunk]:
        pass

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        pass

    async def list_models(self) -> dict[str, list[str]]:
        pass

    def list_requests(self) -> list[tuple[LLMRequest, LLMResponse]]:
        pass

    def list_request_page(
        self,
        limit: int,
        offset: int,
        filters: RequestHistoryFilters | None = None,
    ) -> RequestHistoryPage:
        pass

    def get_request(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        pass

    def get_idempotent_response(
        self,
        endpoint: str,
        idempotency_key: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        pass

    def reserve_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
    ) -> IdempotencyReservation:
        pass

    def complete_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        response: LLMResponse,
    ) -> None:
        pass

    def fail_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        error: str,
    ) -> None:
        pass

    def delete_expired_idempotency_records(self) -> int:
        pass
