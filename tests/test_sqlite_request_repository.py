from concurrent.futures import ThreadPoolExecutor

from adapters.persistence.sqlite_request_repository import (
    SQLiteRequestRepository,
)
from domain.idempotency import IdempotencyConflict, IdempotencyInProgress
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


def test_idempotency_reservation_is_atomic_and_replays_completed_response(
    tmp_path,
):
    repository = SQLiteRequestRepository(
        str(tmp_path / "llm_gateway.sqlite3"),
    )
    endpoint = "/v1/chat/completions"

    reservation = repository.reserve_idempotency_key(
        endpoint=endpoint,
        idempotency_key="idem-atomic",
        request_hash="hash-1",
        request_id="request-1",
    )

    assert reservation.is_reserved

    try:
        repository.reserve_idempotency_key(
            endpoint=endpoint,
            idempotency_key="idem-atomic",
            request_hash="hash-1",
            request_id="request-2",
        )
    except IdempotencyInProgress as error:
        assert "in progress" in str(error)
    else:
        raise AssertionError("expected in-progress idempotency error")

    try:
        repository.reserve_idempotency_key(
            endpoint=endpoint,
            idempotency_key="idem-atomic",
            request_hash="different-hash",
            request_id="request-3",
        )
    except IdempotencyConflict as error:
        assert "different payload" in str(error)
    else:
        raise AssertionError("expected idempotency conflict")

    response = LLMResponse(
        request_id="request-1",
        provider=ProviderName.OLLAMA,
        model="llama3.2:1b",
        status="success",
        content="done",
    )
    repository.complete_idempotency_key(
        endpoint=endpoint,
        idempotency_key="idem-atomic",
        response=response,
    )

    replay = repository.reserve_idempotency_key(
        endpoint=endpoint,
        idempotency_key="idem-atomic",
        request_hash="hash-1",
        request_id="request-4",
    )

    assert replay.is_replay
    assert replay.response == response


def test_concurrent_idempotency_reservations_have_single_winner(tmp_path):
    database_path = str(tmp_path / "llm_gateway.sqlite3")
    SQLiteRequestRepository(database_path)

    def reserve(index):
        repository = SQLiteRequestRepository(database_path)
        try:
            result = repository.reserve_idempotency_key(
                endpoint="/v1/chat/completions",
                idempotency_key="same-key",
                request_hash="same-hash",
                request_id=f"request-{index}",
            )
            return result.status
        except IdempotencyInProgress:
            return "in_progress"

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(reserve, range(10)))

    assert results.count("reserved") == 1
    assert results.count("in_progress") == 9
