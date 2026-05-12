from typing import Protocol

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse


class RequestRepository(Protocol):
    def save(self, request: LLMRequest, response: LLMResponse) -> None:
        pass

    def find_all(self) -> list[tuple[LLMRequest, LLMResponse]]:
        pass

    def find_by_request_id(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        pass
