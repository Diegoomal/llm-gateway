from adapters.observability.sqlite_metrics_recorder import SQLiteMetricsRecorder
from domain.llm_response import TokenUsage


def test_sqlite_metrics_persist_after_recorder_recreation(tmp_path):
    database_path = str(tmp_path / "llm_gateway.sqlite3")
    recorder = SQLiteMetricsRecorder(database_path)

    recorder.record_request(
        provider="ollama",
        model="llama3.2:1b",
        endpoint="/v1/chat/completions",
        status="success",
        duration_seconds=0.2,
        usage=TokenUsage(
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
        ),
    )

    recreated = SQLiteMetricsRecorder(database_path)
    metrics = recreated.render_prometheus()

    assert (
        'llm_requests_total{provider="ollama",model="llama3.2:1b",'
        'status="success",endpoint="/v1/chat/completions"} 1'
    ) in metrics
    assert "llm_request_duration_seconds_bucket" in metrics
    assert (
        'llm_tokens_total{provider="ollama",model="llama3.2:1b",'
        'status="success",endpoint="/v1/chat/completions"} 3.0'
    ) in metrics


def test_sqlite_metrics_persist_idempotency_and_timing_events(tmp_path):
    database_path = str(tmp_path / "llm_gateway.sqlite3")
    recorder = SQLiteMetricsRecorder(database_path)

    recorder.record_idempotency_event("/v1/chat/completions", "in_progress")
    recorder.record_generation_timing(
        provider="ollama",
        model="llama3.2:1b",
        endpoint="/v1/chat/completions",
        status="success",
        first_token_latency_seconds=0.3,
        generation_duration_seconds=0.7,
    )
    recorder.record_cold_start_detected(
        provider="ollama",
        model="llama3.2:1b",
        endpoint="/v1/chat/completions",
        status="success",
    )

    metrics = SQLiteMetricsRecorder(database_path).render_prometheus()

    assert (
        'llm_idempotency_total{endpoint="/v1/chat/completions",'
        'status="in_progress"} 1'
    ) in metrics
    assert "llm_first_token_latency_seconds_bucket" in metrics
    assert "llm_generation_duration_seconds_bucket" in metrics
    assert (
        'llm_cold_start_detected_total{provider="ollama",'
        'model="llama3.2:1b",status="success",'
        'endpoint="/v1/chat/completions"} 1'
    ) in metrics


def test_active_requests_are_not_persisted(tmp_path):
    database_path = str(tmp_path / "llm_gateway.sqlite3")
    recorder = SQLiteMetricsRecorder(database_path)

    recorder.increment_active_requests("ollama", "llama3.2:1b")

    assert (
        'llm_active_requests{provider="ollama",model="llama3.2:1b"} 1'
        in recorder.render_prometheus()
    )
    assert "llm_active_requests" not in (
        SQLiteMetricsRecorder(database_path).render_prometheus()
    )


def test_metric_events_can_expire(tmp_path):
    database_path = str(tmp_path / "llm_gateway.sqlite3")
    recorder = SQLiteMetricsRecorder(
        database_path,
        metric_events_ttl_seconds=1,
    )
    recorder.record_idempotency_event("/v1/chat/completions", "reserved")

    with recorder._connect() as connection:
        connection.execute("UPDATE metric_events SET expires_at = 1")

    metrics = recorder.render_prometheus()

    assert "llm_idempotency_total" not in metrics
