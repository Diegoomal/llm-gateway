from adapters.persistence.sqlite_request_repository import (
    SQLiteRequestRepository,
)
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.provider_name import ProviderName


def test_save_and_find_request_history_in_sqlite(tmp_path):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="llama3.2:1b",
        provider="ollama",
        metadata={"endpoint": "/v1/chat/completions"},
    )
    response = LLMResponse(
        request_id=request.request_id,
        provider=ProviderName.OLLAMA,
        model="llama3.2:1b",
        status="success",
        content="hello",
        usage=TokenUsage(
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        ),
        raw={"done": True},
    )

    repository.save(request, response)

    assert repository.find_all() == [(request, response)]
    assert repository.find_by_request_id(request.request_id) == (
        request,
        response,
    )


def test_find_by_request_id_returns_none_when_sqlite_record_is_missing(
    tmp_path,
):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )

    assert repository.find_by_request_id("missing") is None
