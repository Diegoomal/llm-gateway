import asyncio
import hashlib
import json
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

from adapters.http.rate_limit_middleware import RateLimitMiddleware
from configurator import configure_gateway_container
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, LLMStreamChunk
from domain.request_history import RequestHistoryFilters


container = configure_gateway_container()
app = FastAPI(title=container.settings.app_name)
app.add_middleware(
    RateLimitMiddleware,
    enabled=container.settings.rate_limit_enabled,
    requests_limit=container.settings.rate_limit_requests,
    window_seconds=container.settings.rate_limit_window_seconds,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": container.settings.app_name,
        "env": container.settings.app_env,
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    payload: dict[str, Any],
    idempotency_key: str | None = Header(default=None),
):
    endpoint = "/v1/chat/completions"
    request_hash = _payload_hash(payload)
    existing_response = await _idempotent_record(
        endpoint,
        idempotency_key,
        request_hash,
    )
    if existing_response is not None:
        return existing_response

    metadata = {
        "raw_request": payload,
        "idempotency_key": idempotency_key,
        "request_hash": request_hash,
    }
    if payload.get("cache") is True and not payload.get("stream", False):
        metadata["cache_key"] = request_hash

    request = LLMRequest.chat(
        messages=payload.get("messages", []),
        model=payload.get("model"),
        provider=payload.get("provider"),
        stream=bool(payload.get("stream", False)),
        metadata=metadata,
    )
    if request.stream:
        return StreamingResponse(
            _chat_completion_event_stream(request),
            media_type="text/event-stream",
        )

    response = await container.gateway.chat_completion(request)
    if not response.is_success:
        raise HTTPException(
            status_code=_status_code_for(response),
            detail=_response_to_chat_payload(response),
        )
    return _response_to_chat_payload(response)


async def _chat_completion_event_stream(request: LLMRequest):
    async for chunk in container.gateway.stream_chat_completion(request):
        yield f"data: {json.dumps(_chunk_to_chat_payload(chunk))}\n\n"
        if chunk.finish_reason:
            yield "data: [DONE]\n\n"


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


def _chunk_to_chat_payload(chunk: LLMStreamChunk) -> dict[str, Any]:
    delta = {}
    if chunk.content_delta:
        delta["content"] = chunk.content_delta
    payload = {
        "id": chunk.request_id,
        "object": "chat.completion.chunk",
        "model": chunk.model,
        "provider": chunk.provider.value,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": chunk.finish_reason,
            }
        ],
        "error": chunk.error,
    }
    if chunk.usage.total_tokens:
        payload["usage"] = chunk.usage.__dict__
    return payload


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
async def list_requests(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    provider: str | None = None,
    model: str | None = None,
    status: str | None = None,
    endpoint: str | None = None,
) -> dict[str, Any]:
    page = await asyncio.to_thread(
        container.gateway.list_request_page,
        limit,
        offset,
        RequestHistoryFilters(
            provider=provider,
            model=model,
            status=status,
            endpoint=endpoint,
        ),
    )
    return {
        "object": "list",
        "limit": page.limit,
        "offset": page.offset,
        "total": page.total,
        "data": [
            _history_record(request, response)
            for request, response in page.items
        ],
    }


@app.get("/v1/requests/{request_id}")
async def get_request(request_id: str) -> dict[str, Any]:
    record = await asyncio.to_thread(container.gateway.get_request, request_id)
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


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _idempotent_record(
    endpoint: str,
    idempotency_key: str | None,
    request_hash: str,
):
    if idempotency_key is None:
        return None
    record = await asyncio.to_thread(
        container.gateway.get_idempotent_response,
        endpoint,
        idempotency_key,
    )
    if record is None:
        return None

    request, response = record
    if request.metadata.get("request_hash") != request_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used with a different payload",
        )
    return _response_to_chat_payload(response)


if __name__ == "__main__":
    from adapters.cli.main import run

    asyncio.run(run(container.gateway))
