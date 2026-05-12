from typing import Any

import httpx

from application.ports.llm_provider import LLMProvider
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.provider_name import ProviderName


class LlamaCppProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout_seconds: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model or self.default_model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
        }
        data = await self._post("/v1/chat/completions", payload)
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.LLAMA_CPP,
            model=data.get("model", payload["model"]),
            status="success",
            content=message.get("content", ""),
            usage=TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            raw=data,
        )

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model or self.default_model,
            "input": request.input,
        }
        data = await self._post("/v1/embeddings", payload)
        embeddings = [
            item.get("embedding", [])
            for item in data.get("data", [])
        ]
        usage = data.get("usage", {})

        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.LLAMA_CPP,
            model=data.get("model", payload["model"]),
            status="success",
            embeddings=embeddings,
            usage=TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=0,
                total_tokens=usage.get("total_tokens", 0),
            ),
            raw=data,
        )

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            data = response.json()
        return [model["id"] for model in data.get("data", [])]

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()
