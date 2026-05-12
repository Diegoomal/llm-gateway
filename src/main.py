import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from configurator import configure_gateway_container
from domain.llm_request import LLMRequest


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
    return {
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


if __name__ == "__main__":
    from adapters.cli.main import run

    asyncio.run(run(container.gateway))
