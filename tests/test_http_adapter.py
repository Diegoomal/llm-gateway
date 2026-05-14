from fastapi.testclient import TestClient

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, LLMStreamChunk
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
