import asyncio

from adapters.observability.in_memory_metrics_recorder import (
    InMemoryMetricsRecorder,
)
from adapters.persistence.sqlite_request_repository import (
    SQLiteRequestRepository,
)
from application.services.fallback_service import FallbackService
from application.services.llm_gateway_service import LLMGatewayService
from application.services.observability_service import ObservabilityService
from application.services.routing_service import RoutingService
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.provider_name import ProviderName


class FakeProvider:
    def __init__(self, provider_name: ProviderName, fail: bool = False):
        self.provider_name = provider_name
        self.fail = fail
        self.requests = []

    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError(f"{self.provider_name.value} failed")
        return LLMResponse(
            request_id=request.request_id,
            provider=self.provider_name,
            model=request.model or "missing-model",
            status="success",
            content=f"{self.provider_name.value} response",
            usage=TokenUsage(
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
            ),
        )

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            request_id=request.request_id,
            provider=self.provider_name,
            model=request.model or "missing-model",
            status="success",
            embeddings=[[0.1, 0.2]],
        )

    async def list_models(self) -> list[str]:
        if self.fail:
            raise RuntimeError(f"{self.provider_name.value} failed")
        return [f"{self.provider_name.value}-model"]


def make_gateway(tmp_path, ollama_fail: bool = False):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    metrics = InMemoryMetricsRecorder()
    providers = {
        ProviderName.OLLAMA.value: FakeProvider(
            ProviderName.OLLAMA,
            fail=ollama_fail,
        ),
        ProviderName.LLAMA_CPP.value: FakeProvider(ProviderName.LLAMA_CPP),
    }
    gateway = LLMGatewayService(
        providers=providers,
        routing_service=RoutingService(
            default_provider=ProviderName.OLLAMA,
            default_models={
                ProviderName.OLLAMA: "llama3.2:1b",
                ProviderName.LLAMA_CPP: "local-gguf-model",
            },
            fallback_provider=ProviderName.LLAMA_CPP,
        ),
        fallback_service=FallbackService(providers),
        observability_service=ObservabilityService(metrics),
        request_repository=repository,
    )
    return gateway, providers, repository, metrics


def run(coro):
    return asyncio.run(coro)


def test_chat_completion_uses_default_provider_and_model(tmp_path):
    gateway, providers, repository, metrics = make_gateway(tmp_path)
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    response = run(gateway.chat_completion(request))

    assert response.provider == ProviderName.OLLAMA
    assert response.model == "llama3.2:1b"
    assert response.content == "ollama response"
    assert providers[ProviderName.OLLAMA.value].requests[0].model == "llama3.2:1b"
    saved_request, saved_response = repository.find_by_request_id(
        request.request_id,
    )
    assert saved_request.metadata["endpoint"] == "/v1/chat/completions"
    assert saved_response == response
    assert sum(metrics.requests_total.values()) == 1


def test_explicit_provider_has_priority(tmp_path):
    gateway, providers, _, _ = make_gateway(tmp_path)
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
        provider="llama_cpp",
    )

    response = run(gateway.chat_completion(request))

    assert response.provider == ProviderName.LLAMA_CPP
    assert response.model == "local-gguf-model"
    assert providers[ProviderName.OLLAMA.value].requests == []


def test_fallback_is_used_when_primary_provider_fails(tmp_path):
    gateway, providers, _, metrics = make_gateway(
        tmp_path,
        ollama_fail=True,
    )
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    response = run(gateway.chat_completion(request))

    assert response.provider == ProviderName.LLAMA_CPP
    assert response.model == "local-gguf-model"
    assert len(providers[ProviderName.OLLAMA.value].requests) == 1
    assert len(providers[ProviderName.LLAMA_CPP.value].requests) == 1
    assert sum(metrics.provider_errors_total.values()) == 0


def test_embeddings_are_standardized(tmp_path):
    gateway, _, _, _ = make_gateway(tmp_path)
    request = LLMRequest.embedding(input="hello")

    response = run(gateway.embeddings(request))

    assert response.provider == ProviderName.OLLAMA
    assert response.embeddings == [[0.1, 0.2]]


def test_list_models_groups_by_provider(tmp_path):
    gateway, _, _, _ = make_gateway(tmp_path)

    models = run(gateway.list_models())

    assert models == {
        "ollama": ["ollama-model"],
        "llama_cpp": ["llama_cpp-model"],
    }


def test_list_models_returns_available_providers_when_one_fails(tmp_path):
    gateway, _, _, _ = make_gateway(tmp_path, ollama_fail=True)

    models = run(gateway.list_models())

    assert models == {
        "ollama": [],
        "llama_cpp": ["llama_cpp-model"],
    }
