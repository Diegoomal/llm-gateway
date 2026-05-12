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
    def __init__(
        self,
        provider_name: ProviderName,
        fail: bool = False,
        timeout: bool = False,
        content: str | None = None,
    ):
        self.provider_name = provider_name
        self.fail = fail
        self.timeout = timeout
        self.content = content
        self.requests = []

    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.timeout:
            raise TimeoutError(f"{self.provider_name.value} timed out")
        if self.fail:
            raise RuntimeError(f"{self.provider_name.value} failed")
        return LLMResponse(
            request_id=request.request_id,
            provider=self.provider_name,
            model=request.model or "missing-model",
            status="success",
            content=self.content or f"{self.provider_name.value} response",
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


def make_gateway(
    tmp_path,
    ollama_fail: bool = False,
    ollama_timeout: bool = False,
    llama_fail: bool = False,
    ollama_content: str | None = None,
):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    metrics = InMemoryMetricsRecorder()
    providers = {
        ProviderName.OLLAMA.value: FakeProvider(
            ProviderName.OLLAMA,
            fail=ollama_fail,
            timeout=ollama_timeout,
            content=ollama_content,
        ),
        ProviderName.LLAMA_CPP.value: FakeProvider(
            ProviderName.LLAMA_CPP,
            fail=llama_fail,
        ),
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


def test_llama_cpp_provider_path_is_prepared(tmp_path):
    gateway, providers, _, _ = make_gateway(tmp_path)
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
        provider="llama_cpp",
    )

    response = run(gateway.chat_completion(request))

    assert response.provider == ProviderName.LLAMA_CPP
    assert response.model == "local-gguf-model"
    assert len(providers[ProviderName.LLAMA_CPP.value].requests) == 1


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
    assert response.fallback_used is True
    assert response.fallback_from_provider == ProviderName.OLLAMA
    assert response.fallback_from_model == "llama3.2:1b"
    assert len(providers[ProviderName.OLLAMA.value].requests) == 1
    assert len(providers[ProviderName.LLAMA_CPP.value].requests) == 1
    assert sum(metrics.provider_errors_total.values()) == 0
    assert sum(metrics.fallbacks_total.values()) == 1


def test_provider_error_is_controlled_persisted_and_metered(tmp_path):
    gateway, _, repository, metrics = make_gateway(
        tmp_path,
        ollama_fail=True,
        llama_fail=True,
    )
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    response = run(gateway.chat_completion(request))

    assert response.status == "error"
    assert response.error
    assert response.error_type == "provider_error"
    saved_request, saved_response = repository.find_by_request_id(
        request.request_id,
    )
    assert saved_request.metadata["endpoint"] == "/v1/chat/completions"
    assert saved_response.status == "error"
    assert sum(metrics.provider_errors_total.values()) == 1


def test_invalid_model_returns_controlled_error(tmp_path):
    gateway, _, repository, metrics = make_gateway(
        tmp_path,
        ollama_fail=True,
        llama_fail=True,
    )
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="model-does-not-exist",
        provider="ollama",
    )

    response = run(gateway.chat_completion(request))

    assert response.status == "error"
    assert response.model == "local-gguf-model"
    assert response.error
    assert repository.find_by_request_id(request.request_id)[1].status == (
        "error"
    )
    assert sum(metrics.provider_errors_total.values()) == 1


def test_provider_timeout_is_classified(tmp_path):
    gateway, _, repository, metrics = make_gateway(
        tmp_path,
        ollama_timeout=True,
        llama_fail=True,
    )
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    response = run(gateway.chat_completion(request))

    assert response.status == "error"
    assert response.error_type == "provider_error"
    assert repository.find_by_request_id(request.request_id)[1].error
    assert sum(metrics.provider_errors_total.values()) == 1


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


def classify_exact_content(actual: str, expected: str) -> str:
    if actual.strip() == expected:
        return "PASS"
    if actual.strip():
        return "PASS_WITH_WARNING"
    return "FAIL"


def test_exact_content_validation_can_warn_on_model_drift(tmp_path):
    gateway, _, _, _ = make_gateway(
        tmp_path,
        ollama_content="It's a beautiful day.",
    )
    request = LLMRequest.chat(
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: perfect day",
            }
        ],
    )

    response = run(gateway.chat_completion(request))

    assert response.is_success
    assert classify_exact_content(response.content, "perfect day") == (
        "PASS_WITH_WARNING"
    )


def test_request_history_is_available_from_gateway(tmp_path):
    gateway, _, _, _ = make_gateway(tmp_path)
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    response = run(gateway.chat_completion(request))

    assert gateway.list_requests()[0][1] == response
    assert gateway.get_request(request.request_id)[1] == response
    assert gateway.get_request("missing") is None
