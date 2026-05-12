from typing import Protocol

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse


class ForManagingLLMRequests(Protocol):
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        pass

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        pass

    async def list_models(self) -> dict[str, list[str]]:
        pass

    def list_requests(self) -> list[tuple[LLMRequest, LLMResponse]]:
        pass

    def get_request(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        pass
