import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from configurator import configure_gateway_container
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse


container = configure_gateway_container()
app = FastAPI(title=container.settings.app_name)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": container.settings.app_name,
        "env": container.settings.app_env,
    }


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
    request = LLMRequest.chat(
        messages=payload.get("messages", []),
        model=payload.get("model"),
        provider=payload.get("provider"),
        metadata={"raw_request": payload},
    )
    response = await container.gateway.chat_completion(request)
    if not response.is_success:
        raise HTTPException(
            status_code=_status_code_for(response),
            detail=_response_to_chat_payload(response),
        )
    return _response_to_chat_payload(response)


def _response_to_chat_payload(response: LLMResponse) -> dict[str, Any]:
    return {
        "id": response.request_id,
        "object": "chat.completion",
        "model": response.model,
        "provider": response.provider.value,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.content or "",
                },
                "finish_reason": (
                    "stop" if response.is_success else "error"
                ),
            }
        ],
        "usage": response.usage.__dict__,
        "error": response.error,
    }


@app.post("/v1/embeddings")
async def embeddings(payload: dict[str, Any]) -> dict[str, Any]:
    request = LLMRequest.embedding(
        input=payload.get("input", ""),
        model=payload.get("model"),
        provider=payload.get("provider"),
        metadata={"raw_request": payload},
    )
    response = await container.gateway.embeddings(request)
    payload = {
        "object": "list",
        "model": response.model,
        "provider": response.provider.value,
        "data": [
            {
                "object": "embedding",
                "index": index,
                "embedding": embedding,
            }
            for index, embedding in enumerate(response.embeddings or [])
        ],
        "usage": response.usage.__dict__,
        "error": response.error,
    }
    if not response.is_success:
        raise HTTPException(
            status_code=_status_code_for(response),
            detail=payload,
        )
    return payload


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    models = await container.gateway.list_models()
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "owned_by": provider,
            }
            for provider, provider_models in models.items()
            for model in provider_models
        ],
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return container.metrics_recorder.render_prometheus()


@app.get("/v1/requests")
async def list_requests() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            _history_record(request, response)
            for request, response in container.gateway.list_requests()
        ],
    }


@app.get("/v1/requests/{request_id}")
async def get_request(request_id: str) -> dict[str, Any]:
    record = container.gateway.get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Request not found")
    request, response = record
    return _history_record(request, response)


def _history_record(
    request: LLMRequest,
    response: LLMResponse,
) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "trace_id": response.trace_id,
        "provider": response.provider.value,
        "model": response.model,
        "endpoint": request.metadata.get("endpoint"),
        "status": response.status,
        "error": response.error,
        "fallback_used": response.fallback_used,
        "latency_ms": response.latency_ms,
        "usage": response.usage.__dict__,
    }


def _status_code_for(response: LLMResponse) -> int:
    if response.error_type == "timeout":
        return 504
    return 502


if __name__ == "__main__":
    from adapters.cli.main import run

    asyncio.run(run(container.gateway))
