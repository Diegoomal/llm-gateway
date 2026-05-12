from typing import Protocol

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse


class LLMProvider(Protocol):
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        pass

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        pass

    async def list_models(self) -> list[str]:
        pass
