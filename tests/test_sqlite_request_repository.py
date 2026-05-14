from adapters.persistence.sqlite_request_repository import (
    SQLiteRequestRepository,
)
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.provider_name import ProviderName
from domain.request_history import RequestHistoryFilters


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


def test_find_page_applies_pagination_and_filters(tmp_path):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    first = LLMRequest.chat(
        messages=[{"role": "user", "content": "first"}],
        model="llama3.2:1b",
        provider="ollama",
        metadata={"endpoint": "/v1/chat/completions"},
    )
    second = LLMRequest.chat(
        messages=[{"role": "user", "content": "second"}],
        model="local-gguf-model",
        provider="llama_cpp",
        metadata={"endpoint": "/v1/chat/completions"},
    )
    repository.save(
        first,
        LLMResponse(
            request_id=first.request_id,
            provider=ProviderName.OLLAMA,
            model="llama3.2:1b",
            status="success",
            content="first",
        ),
    )
    repository.save(
        second,
        LLMResponse(
            request_id=second.request_id,
            provider=ProviderName.LLAMA_CPP,
            model="local-gguf-model",
            status="success",
            content="second",
        ),
    )

    page = repository.find_page(
        limit=1,
        offset=0,
        filters=RequestHistoryFilters(provider="llama_cpp"),
    )

    assert page.total == 1
    assert page.limit == 1
    assert page.items[0][0].request_id == second.request_id


def test_find_by_idempotency_key_returns_existing_record(tmp_path):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    request = LLMRequest.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="llama3.2:1b",
        provider="ollama",
        metadata={
            "endpoint": "/v1/chat/completions",
            "idempotency_key": "idem-1",
            "request_hash": "hash-1",
        },
    )
    response = LLMResponse(
        request_id=request.request_id,
        provider=ProviderName.OLLAMA,
        model="llama3.2:1b",
        status="success",
        content="hello",
    )

    repository.save(request, response)

    assert repository.find_by_idempotency_key(
        "/v1/chat/completions",
        "idem-1",
    ) == (request, response)
