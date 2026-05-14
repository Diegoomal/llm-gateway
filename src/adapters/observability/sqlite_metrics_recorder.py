import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from time import time
from typing import Any

from adapters.observability.prometheus_renderer import (
    metric_labels,
    new_histogram,
    observe_histogram,
    render_histogram,
)
from domain.llm_response import TokenUsage


class SQLiteMetricsRecorder:
    def __init__(
        self,
        database_path: str,
        sqlite_busy_timeout_ms: int = 5000,
        metric_events_ttl_seconds: int = 604800,
    ):
        self.database_path = database_path
        self.sqlite_busy_timeout_ms = sqlite_busy_timeout_ms
        self.metric_events_ttl_seconds = metric_events_ttl_seconds
        self.active_requests = defaultdict(int)
        self._ensure_parent_dir()
        self._initialize_schema()

    def increment_active_requests(self, provider: str, model: str) -> None:
        self.active_requests[(provider, model)] += 1

    def decrement_active_requests(self, provider: str, model: str) -> None:
        key = (provider, model)
        self.active_requests[key] = max(0, self.active_requests[key] - 1)

    def record_request(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
        duration_seconds: float,
        usage: TokenUsage,
    ) -> None:
        self._record_event(
            event_type="request_completed",
            provider=provider,
            model=model,
            endpoint=endpoint,
            status=status,
            value=duration_seconds,
        )
        self._record_event(
            event_type="tokens_used",
            provider=provider,
            model=model,
            endpoint=endpoint,
            status=status,
            value=usage.total_tokens,
            labels={
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
            },
        )
        if duration_seconds > 0 and usage.total_tokens > 0:
            self._record_event(
                event_type="tokens_per_second",
                provider=provider,
                model=model,
                endpoint=endpoint,
                status=status,
                value=usage.total_tokens / duration_seconds,
            )

    def record_provider_error(
        self,
        provider: str,
        model: str,
        endpoint: str,
    ) -> None:
        self._record_event(
            event_type="provider_error",
            provider=provider,
            model=model,
            endpoint=endpoint,
            status="error",
        )

    def record_fallback(
        self,
        from_provider: str,
        from_model: str,
        to_provider: str,
        to_model: str,
        status: str,
    ) -> None:
        self._record_event(
            event_type="fallback_used",
            provider=to_provider,
            model=to_model,
            status=status,
            labels={
                "from_provider": from_provider,
                "from_model": from_model,
                "to_provider": to_provider,
                "to_model": to_model,
            },
        )

    def record_idempotency_event(self, endpoint: str, status: str) -> None:
        self._record_event(
            event_type="idempotency_event",
            endpoint=endpoint,
            status=status,
        )

    def record_generation_timing(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
        first_token_latency_seconds: float | None = None,
        generation_duration_seconds: float | None = None,
    ) -> None:
        if first_token_latency_seconds is not None:
            self._record_event(
                event_type="first_token_latency",
                provider=provider,
                model=model,
                endpoint=endpoint,
                status=status,
                value=first_token_latency_seconds,
            )
        if generation_duration_seconds is not None:
            self._record_event(
                event_type="generation_duration",
                provider=provider,
                model=model,
                endpoint=endpoint,
                status=status,
                value=generation_duration_seconds,
            )

    def record_cold_start_detected(
        self,
        provider: str,
        model: str,
        endpoint: str,
        status: str,
    ) -> None:
        self._record_event(
            event_type="cold_start_detected",
            provider=provider,
            model=model,
            endpoint=endpoint,
            status=status,
        )

    def render_prometheus(self) -> str:
        rows = self._metric_events()
        lines = []

        request_counts = defaultdict(int)
        request_duration = defaultdict(float)
        request_duration_histogram = new_histogram()
        provider_errors = defaultdict(int)
        tokens_total = defaultdict(float)
        tokens_per_second = defaultdict(float)
        fallbacks = defaultdict(int)
        idempotency = defaultdict(int)
        first_token_latency = defaultdict(float)
        first_token_latency_histogram = new_histogram()
        generation_duration = defaultdict(float)
        generation_duration_histogram = new_histogram()
        cold_starts = defaultdict(int)

        for row in rows:
            event_type = row["event_type"]
            labels = (
                row["provider"] or "",
                row["model"] or "",
                row["status"] or "",
                row["endpoint"] or "",
            )
            value = row["value"] or 0.0
            count = row["count"] or 1
            extra_labels = json.loads(row["labels_json"] or "{}")

            if event_type == "request_completed":
                request_counts[labels] += count
                request_duration[labels] += value
                observe_histogram(request_duration_histogram, labels, value)
            elif event_type == "provider_error":
                provider_errors[
                    (
                        row["provider"] or "",
                        row["model"] or "",
                        row["endpoint"] or "",
                    )
                ] += count
            elif event_type == "tokens_used":
                tokens_total[labels] += value
            elif event_type == "tokens_per_second":
                tokens_per_second[labels] = value
            elif event_type == "fallback_used":
                fallbacks[
                    (
                        extra_labels.get("from_provider", ""),
                        extra_labels.get("from_model", ""),
                        extra_labels.get("to_provider", row["provider"] or ""),
                        extra_labels.get("to_model", row["model"] or ""),
                        row["status"] or "",
                    )
                ] += count
            elif event_type == "idempotency_event":
                idempotency[(row["endpoint"] or "", row["status"] or "")] += (
                    count
                )
            elif event_type == "first_token_latency":
                first_token_latency[labels] += value
                observe_histogram(first_token_latency_histogram, labels, value)
            elif event_type == "generation_duration":
                generation_duration[labels] += value
                observe_histogram(generation_duration_histogram, labels, value)
            elif event_type == "cold_start_detected":
                cold_starts[labels] += count

        self._render_standard_metric(lines, "llm_requests_total", request_counts)
        self._render_standard_metric(
            lines,
            "llm_request_duration_seconds",
            request_duration,
        )
        render_histogram(
            lines,
            "llm_request_duration_seconds",
            request_duration_histogram,
        )
        self._render_provider_errors(lines, provider_errors)
        self._render_standard_metric(lines, "llm_tokens_total", tokens_total)
        self._render_standard_metric(
            lines,
            "llm_tokens_per_second",
            tokens_per_second,
        )
        self._render_active_requests(lines)
        self._render_fallbacks(lines, fallbacks)
        self._render_idempotency(lines, idempotency)
        self._render_standard_metric(
            lines,
            "llm_first_token_latency_seconds",
            first_token_latency,
        )
        render_histogram(
            lines,
            "llm_first_token_latency_seconds",
            first_token_latency_histogram,
        )
        self._render_standard_metric(
            lines,
            "llm_generation_duration_seconds",
            generation_duration,
        )
        render_histogram(
            lines,
            "llm_generation_duration_seconds",
            generation_duration_histogram,
        )
        self._render_standard_metric(
            lines,
            "llm_cold_start_detected_total",
            cold_starts,
        )

        return "\n".join(lines) + "\n"

    def _record_event(
        self,
        event_type: str,
        provider: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        status: str | None = None,
        value: float | None = None,
        count: int = 1,
        labels: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            self._delete_expired_metric_events(connection)
            connection.execute(
                """
                INSERT INTO metric_events (
                    event_type,
                    provider,
                    model,
                    endpoint,
                    status,
                    value,
                    count,
                    labels_json,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    provider,
                    model,
                    endpoint,
                    status,
                    value,
                    count,
                    json.dumps(labels or {}, sort_keys=True),
                    self._event_expires_at(),
                ),
            )

    def _metric_events(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            self._delete_expired_metric_events(connection)
            return connection.execute(
                """
                SELECT event_type, provider, model, endpoint, status,
                       value, count, labels_json
                FROM metric_events
                ORDER BY id ASC
                """
            ).fetchall()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.sqlite_busy_timeout_ms / 1000,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self.sqlite_busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys = ON")
        if self.database_path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _ensure_parent_dir(self) -> None:
        if self.database_path == ":memory:":
            return
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metric_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    endpoint TEXT,
                    status TEXT,
                    value REAL,
                    count INTEGER NOT NULL DEFAULT 1,
                    labels_json TEXT,
                    expires_at INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metric_events_type_labels
                ON metric_events(event_type, provider, model, endpoint, status)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metric_events_created_at
                ON metric_events(created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metric_events_expires_at
                ON metric_events(expires_at)
                """
            )

    def _delete_expired_metric_events(
        self,
        connection: sqlite3.Connection,
    ) -> sqlite3.Cursor:
        return connection.execute(
            """
            DELETE FROM metric_events
            WHERE expires_at IS NOT NULL AND expires_at <= ?
            """,
            (int(time()),),
        )

    def _event_expires_at(self) -> int | None:
        if self.metric_events_ttl_seconds <= 0:
            return None
        return int(time()) + self.metric_events_ttl_seconds

    def _render_standard_metric(
        self,
        lines: list[str],
        name: str,
        values,
    ) -> None:
        for labels, value in sorted(values.items()):
            provider, model, status, endpoint = labels
            lines.append(
                f"{name}{metric_labels(provider, model, status, endpoint)} "
                f"{value}"
            )

    def _render_provider_errors(self, lines: list[str], values) -> None:
        for labels, value in sorted(values.items()):
            provider, model, endpoint = labels
            lines.append(
                "llm_provider_errors_total"
                f'{metric_labels(provider, model, "error", endpoint)} {value}'
            )

    def _render_active_requests(self, lines: list[str]) -> None:
        for labels, value in sorted(self.active_requests.items()):
            provider, model = labels
            lines.append(
                "llm_active_requests"
                f'{{provider="{provider}",model="{model}"}} {value}'
            )

    def _render_fallbacks(self, lines: list[str], values) -> None:
        for labels, value in sorted(values.items()):
            from_provider, from_model, to_provider, to_model, status = labels
            lines.append(
                "llm_fallbacks_total"
                "{"
                f'from_provider="{from_provider}",'
                f'from_model="{from_model}",'
                f'to_provider="{to_provider}",'
                f'to_model="{to_model}",'
                f'status="{status}"'
                f"}} {value}"
            )

    def _render_idempotency(self, lines: list[str], values) -> None:
        for labels, value in sorted(values.items()):
            endpoint, status = labels
            lines.append(
                "llm_idempotency_total"
                f'{{endpoint="{endpoint}",status="{status}"}} {value}'
            )
