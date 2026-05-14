import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from fastapi.testclient import TestClient

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
from domain.idempotency import IdempotencyInProgress, IdempotencyReservation
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, LLMStreamChunk, TokenUsage
from domain.provider_name import ProviderName
from domain.request_history import RequestHistoryPage
from main import _payload_hash, app, container


class FakeGateway:
    def __init__(self):
        self.request = LLMRequest.chat(
            messages=[{"role": "user", "content": "hello"}],
            model="llama3.2:1b",
            provider="ollama",
            metadata={"endpoint": "/v1/chat/completions"},
        )
        self.response = LLMResponse(
            request_id=self.request.request_id,
            provider=ProviderName.OLLAMA,
            model="llama3.2:1b",
            status="success",
            content="hello",
            trace_id="trace-test",
            latency_ms=12,
        )
        self.idempotent_record = None

    async def chat_completion(self, request):
        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=request.model,
            status="error",
            error="provider unavailable",
            error_type="provider_error",
        )

    async def stream_chat_completion(self, request):
        yield LLMStreamChunk(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=request.model,
            content_delta="hello",
        )
        yield LLMStreamChunk(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=request.model,
            content_delta=" world",
            finish_reason="stop",
        )

    async def embeddings(self, request):
        return self.response

    async def list_models(self):
        return {"ollama": ["llama3.2:1b"]}

    def list_requests(self):
        return [(self.request, self.response)]

    def list_request_page(self, limit, offset, filters=None):
        return RequestHistoryPage(
            items=[(self.request, self.response)],
            total=1,
            limit=limit,
            offset=offset,
        )

    def get_request(self, request_id):
        if request_id == self.request.request_id:
            return self.request, self.response
        return None

    def get_idempotent_response(self, endpoint, idempotency_key):
        return self.idempotent_record

    def reserve_idempotency_key(
        self,
        endpoint,
        idempotency_key,
        request_hash,
        request_id,
    ):
        if self.idempotent_record is None:
            return IdempotencyReservation(status="reserved")
        return IdempotencyReservation(
            status="replayed",
            response=self.idempotent_record[1],
        )

    def complete_idempotency_key(self, endpoint, idempotency_key, response):
        self.idempotent_record = (self.request, response)

    def fail_idempotency_key(self, endpoint, idempotency_key, error):
        pass


class InProgressGateway(FakeGateway):
    def __init__(self):
        super().__init__()
        self.executions = 0
        self.in_progress = False
        self.lock = Lock()

    async def chat_completion(self, request):
        self.executions += 1
        time.sleep(0.1)
        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=request.model,
            status="success",
            content="completed",
        )

    def reserve_idempotency_key(
        self,
        endpoint,
        idempotency_key,
        request_hash,
        request_id,
    ):
        with self.lock:
            if self.in_progress:
                raise IdempotencyInProgress(
                    "Request with this Idempotency-Key is still in progress",
                )
            self.in_progress = True
            return IdempotencyReservation(status="reserved")

    def complete_idempotency_key(self, endpoint, idempotency_key, response):
        self.in_progress = False
        self.idempotent_record = (self.request, response)


class SlowProvider:
    def __init__(self):
        self.requests = []

    async def chat_completion(self, request):
        self.requests.append(request)
        await asyncio.sleep(0.1)
        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=request.model,
            status="success",
            content="completed",
            usage=TokenUsage(total_tokens=1),
        )

    async def stream_chat_completion(self, request):
        if False:
            yield

    async def embeddings(self, request):
        return await self.chat_completion(request)

    async def list_models(self):
        return ["llama3.2:1b"]


def make_real_gateway(tmp_path):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    metrics = InMemoryMetricsRecorder()
    provider = SlowProvider()
    providers = {ProviderName.OLLAMA.value: provider}
    gateway = LLMGatewayService(
        providers=providers,
        routing_service=RoutingService(
            default_provider=ProviderName.OLLAMA,
            default_models={ProviderName.OLLAMA: "llama3.2:1b"},
            fallback_provider=None,
        ),
        fallback_service=FallbackService(providers),
        observability_service=ObservabilityService(metrics),
        request_repository=repository,
    )
    return gateway, provider


def test_http_error_response_is_controlled():
    original_gateway = container.gateway
    object.__setattr__(container, "gateway", FakeGateway())
    try:
        client = TestClient(app)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "llama3.2:1b",
                "provider": "ollama",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        assert response.status_code == 502
        assert response.json()["detail"]["error"] == "provider unavailable"
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_http_stream_response_uses_openai_compatible_sse():
    original_gateway = container.gateway
    object.__setattr__(container, "gateway", FakeGateway())
    try:
        client = TestClient(app)

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "llama3.2:1b",
                "provider": "ollama",
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        ) as response:
            body = response.read().decode()

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "text/event-stream",
        )
        assert '"object": "chat.completion.chunk"' in body
        assert '"content": "hello"' in body
        assert '"content": " world"' in body
        assert "data: [DONE]" in body
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_streaming_request_rejects_idempotency_key():
    original_gateway = container.gateway
    object.__setattr__(container, "gateway", FakeGateway())
    try:
        client = TestClient(app)

        response = client.post(
            "/v1/chat/completions",
            headers={"Idempotency-Key": "stream-key"},
            json={
                "model": "llama3.2:1b",
                "provider": "ollama",
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        assert response.status_code == 400
        assert "not supported for streaming" in response.json()["detail"]
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_request_history_endpoints_return_persisted_records():
    original_gateway = container.gateway
    fake_gateway = FakeGateway()
    object.__setattr__(container, "gateway", fake_gateway)
    try:
        client = TestClient(app)

        list_response = client.get("/v1/requests")
        get_response = client.get(
            f"/v1/requests/{fake_gateway.request.request_id}",
        )
        missing_response = client.get("/v1/requests/missing")

        assert list_response.status_code == 200
        assert list_response.json()["data"][0]["trace_id"] == "trace-test"
        assert get_response.status_code == 200
        assert get_response.json()["request_id"] == (
            fake_gateway.request.request_id
        )
        assert missing_response.status_code == 404
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_request_history_endpoint_accepts_pagination_params():
    original_gateway = container.gateway
    fake_gateway = FakeGateway()
    object.__setattr__(container, "gateway", fake_gateway)
    try:
        client = TestClient(app)

        response = client.get("/v1/requests?limit=1&offset=0&provider=ollama")

        assert response.status_code == 200
        assert response.json()["limit"] == 1
        assert response.json()["offset"] == 0
        assert response.json()["total"] == 1
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_idempotency_key_replays_existing_response():
    original_gateway = container.gateway
    fake_gateway = FakeGateway()
    request_payload = {
        "model": "llama3.2:1b",
        "provider": "ollama",
        "messages": [{"role": "user", "content": "hello"}],
    }
    request = LLMRequest.chat(
        messages=request_payload["messages"],
        model=request_payload["model"],
        provider=request_payload["provider"],
        metadata={"request_hash": _payload_hash(request_payload)},
    )
    response = LLMResponse(
        request_id=request.request_id,
        provider=ProviderName.OLLAMA,
        model="llama3.2:1b",
        status="success",
        content="cached",
    )
    fake_gateway.idempotent_record = (request, response)
    object.__setattr__(container, "gateway", fake_gateway)
    try:
        client = TestClient(app)

        result = client.post(
            "/v1/chat/completions",
            headers={"Idempotency-Key": "same-key"},
            json=request_payload,
        )

        assert result.status_code == 200
        assert result.json()["choices"][0]["message"]["content"] == "cached"
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_concurrent_idempotency_425_includes_retry_after():
    original_gateway = container.gateway
    fake_gateway = InProgressGateway()
    object.__setattr__(container, "gateway", fake_gateway)
    try:
        client = TestClient(app)
        request_payload = {
            "model": "llama3.2:1b",
            "provider": "ollama",
            "messages": [{"role": "user", "content": "hello"}],
        }

        def post():
            return client.post(
                "/v1/chat/completions",
                headers={"Idempotency-Key": "same-key"},
                json=request_payload,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: post(), range(2)))

        too_early = [
            response for response in responses if response.status_code == 425
        ]
        success = [
            response for response in responses if response.status_code == 200
        ]

        assert len(too_early) == 1
        assert len(success) == 1
        assert too_early[0].json()["detail"] == (
            "Request with this Idempotency-Key is still in progress"
        )
        assert too_early[0].headers["Retry-After"] == "1"
        assert fake_gateway.executions == 1
    finally:
        object.__setattr__(container, "gateway", original_gateway)


def test_concurrent_http_idempotency_uses_single_real_execution(tmp_path):
    original_gateway = container.gateway
    gateway, provider = make_real_gateway(tmp_path)
    object.__setattr__(container, "gateway", gateway)
    try:
        client = TestClient(app)
        request_payload = {
            "model": "llama3.2:1b",
            "provider": "ollama",
            "messages": [{"role": "user", "content": "hello"}],
        }

        def post():
            return client.post(
                "/v1/chat/completions",
                headers={"Idempotency-Key": "real-key"},
                json=request_payload,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: post(), range(2)))

        assert sorted(response.status_code for response in responses) == [
            200,
            425,
        ]
        assert len(provider.requests) == 1
        too_early = next(
            response for response in responses if response.status_code == 425
        )
        assert too_early.headers["Retry-After"] == "1"

        replay = post()

        assert replay.status_code == 200
        assert replay.json()["choices"][0]["message"]["content"] == (
            "completed"
        )
        assert len(provider.requests) == 1
    finally:
        object.__setattr__(container, "gateway", original_gateway)
