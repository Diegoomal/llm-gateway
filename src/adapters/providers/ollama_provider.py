import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from application.ports.llm_provider import LLMProvider
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, LLMStreamChunk, TokenUsage
from domain.provider_name import ProviderName


class OllamaProvider(LLMProvider):
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
            "stream": request.stream,
        }
        data = await self._post("/api/chat", payload)
        message = data.get("message", {})
        usage = TokenUsage(
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_tokens=(
                data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            ),
        )

        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=payload["model"],
            status="success",
            content=message.get("content", ""),
            usage=usage,
            provider_status_code=200,
            raw=data,
        )

    async def stream_chat_completion(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload = {
            "model": request.model or self.default_model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    detail = (await response.aread()).decode()[:300]
                    raise RuntimeError(
                        f"ollama returned {response.status_code}: {detail}"
                    ) from error

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    usage = TokenUsage(
                        prompt_tokens=data.get("prompt_eval_count", 0),
                        completion_tokens=data.get("eval_count", 0),
                        total_tokens=(
                            data.get("prompt_eval_count", 0)
                            + data.get("eval_count", 0)
                        ),
                    )
                    yield LLMStreamChunk(
                        request_id=request.request_id,
                        provider=ProviderName.OLLAMA,
                        model=payload["model"],
                        content_delta=message.get("content", ""),
                        finish_reason="stop" if data.get("done") else None,
                        usage=usage,
                        raw=data,
                    )

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model or self.default_model,
            "input": request.input,
        }
        data = await self._post("/api/embed", payload)
        embeddings = data.get("embeddings") or [data.get("embedding", [])]

        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=payload["model"],
            status="success",
            embeddings=embeddings,
            provider_status_code=200,
            raw=data,
        )

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
        return [model["name"] for model in data.get("models", [])]

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                detail = response.text[:300]
                raise RuntimeError(
                    f"ollama returned {response.status_code}: {detail}"
                ) from error
            return response.json()
