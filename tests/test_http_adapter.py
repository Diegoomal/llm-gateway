from fastapi.testclient import TestClient

from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse
from domain.provider_name import ProviderName
from main import app, container


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

    async def chat_completion(self, request):
        return LLMResponse(
            request_id=request.request_id,
            provider=ProviderName.OLLAMA,
            model=request.model,
            status="error",
            error="provider unavailable",
            error_type="provider_error",
        )

    async def embeddings(self, request):
        return self.response

    async def list_models(self):
        return {"ollama": ["llama3.2:1b"]}

    def list_requests(self):
        return [(self.request, self.response)]

    def get_request(self, request_id):
        if request_id == self.request.request_id:
            return self.request, self.response
        return None


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
