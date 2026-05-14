import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from time import time
from typing import Any

from domain.idempotency import (
    IdempotencyConflict,
    IdempotencyInProgress,
    IdempotencyReservation,
)
from domain.llm_request import LLMMessage, LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.provider_name import ProviderName
from domain.request_history import RequestHistoryFilters, RequestHistoryPage


class SQLiteRequestRepository:
    def __init__(
        self,
        database_path: str,
        idempotency_record_ttl_seconds: int = 86400,
        sqlite_busy_timeout_ms: int = 5000,
    ):
        self.database_path = database_path
        self.idempotency_record_ttl_seconds = idempotency_record_ttl_seconds
        self.sqlite_busy_timeout_ms = sqlite_busy_timeout_ms
        self._ensure_parent_dir()
        self._initialize_schema()

    def save(self, request: LLMRequest, response: LLMResponse) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO llm_requests (
                    request_id,
                    provider,
                    model,
                    status,
                    endpoint,
                    error,
                    trace_id,
                    latency_ms,
                    provider_status_code,
                    fallback_used,
                    idempotency_key,
                    request_hash,
                    cache_key,
                    request_payload,
                    response_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    response.provider.value,
                    response.model,
                    response.status,
                    request.metadata.get("endpoint"),
                    response.error,
                    response.trace_id or request.metadata.get("trace_id"),
                    response.latency_ms,
                    response.provider_status_code,
                    int(response.fallback_used),
                    request.metadata.get("idempotency_key"),
                    request.metadata.get("request_hash"),
                    request.metadata.get("cache_key"),
                    json.dumps(self._request_to_dict(request)),
                    json.dumps(self._response_to_dict(response)),
                ),
            )

    def find_all(self) -> list[tuple[LLMRequest, LLMResponse]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT request_payload, response_payload
                FROM llm_requests
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def find_page(
        self,
        limit: int,
        offset: int,
        filters: RequestHistoryFilters | None = None,
    ) -> RequestHistoryPage:
        filters = filters or RequestHistoryFilters()
        where, params = self._where_clause(filters)
        limit = min(max(limit, 1), 200)
        offset = max(offset, 0)
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) AS total FROM llm_requests {where}",
                params,
            ).fetchone()["total"]
            rows = connection.execute(
                f"""
                SELECT request_payload, response_payload
                FROM llm_requests
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return RequestHistoryPage(
            items=[self._row_to_record(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def find_by_request_id(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT request_payload, response_payload
                FROM llm_requests
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_record(row)

    def find_by_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT request_payload, response_payload
                FROM llm_requests
                WHERE endpoint = ? AND idempotency_key = ?
                """,
                (endpoint, idempotency_key),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_record(row)

    def reserve_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
    ) -> IdempotencyReservation:
        with self._connect() as connection:
            self._delete_expired_idempotency_records(connection)
            try:
                connection.execute(
                    """
                    INSERT INTO idempotency_records (
                        endpoint,
                        idempotency_key,
                        request_hash,
                        request_id,
                        status,
                        expires_at
                    )
                    VALUES (?, ?, ?, ?, 'in_progress', ?)
                    """,
                    (
                        endpoint,
                        idempotency_key,
                        request_hash,
                        request_id,
                        self._idempotency_expires_at(),
                    ),
                )
                return IdempotencyReservation(status="reserved")
            except sqlite3.IntegrityError:
                row = connection.execute(
                    """
                    SELECT request_hash, status, response_payload, error
                    FROM idempotency_records
                    WHERE endpoint = ? AND idempotency_key = ?
                    """,
                    (endpoint, idempotency_key),
                ).fetchone()

        if row is None:
            raise IdempotencyInProgress(
                "Idempotency-Key reservation is temporarily unavailable"
            )
        if row["request_hash"] != request_hash:
            raise IdempotencyConflict(
                "Idempotency-Key was already used with a different payload"
            )
        if row["status"] == "completed" and row["response_payload"]:
            return IdempotencyReservation(
                status="replayed",
                response=self._response_from_dict(
                    json.loads(row["response_payload"]),
                ),
            )
        if row["status"] == "failed":
            raise IdempotencyInProgress(
                row["error"] or "Request with this Idempotency-Key failed"
            )
        raise IdempotencyInProgress(
            "Request with this Idempotency-Key is still in progress"
        )

    def complete_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        response: LLMResponse,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE idempotency_records
                SET status = 'completed',
                    response_payload = ?,
                    error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE endpoint = ? AND idempotency_key = ?
                """,
                (
                    json.dumps(self._response_to_dict(response)),
                    endpoint,
                    idempotency_key,
                ),
            )

    def fail_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        error: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE idempotency_records
                SET status = 'failed',
                    error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE endpoint = ? AND idempotency_key = ?
                """,
                (error, endpoint, idempotency_key),
            )

    def delete_expired_idempotency_records(self) -> int:
        with self._connect() as connection:
            cursor = self._delete_expired_idempotency_records(connection)
            return cursor.rowcount

    def find_cache_entry(self, cache_key: str) -> LLMResponse | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT response_payload
                FROM llm_requests
                WHERE cache_key = ? AND status = 'success'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return self._response_from_dict(json.loads(row["response_payload"]))

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

    def _delete_expired_idempotency_records(
        self,
        connection: sqlite3.Connection,
    ) -> sqlite3.Cursor:
        return connection.execute(
            """
            DELETE FROM idempotency_records
            WHERE expires_at IS NOT NULL AND expires_at <= ?
            """,
            (int(time()),),
        )

    def _idempotency_expires_at(self) -> int | None:
        if self.idempotency_record_ttl_seconds <= 0:
            return None
        return int(time()) + self.idempotency_record_ttl_seconds

    def _ensure_parent_dir(self) -> None:
        if self.database_path == ":memory:":
            return
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_requests (
                    request_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    endpoint TEXT,
                    error TEXT,
                    trace_id TEXT,
                    latency_ms INTEGER,
                    provider_status_code INTEGER,
                    fallback_used INTEGER NOT NULL DEFAULT 0,
                    idempotency_key TEXT,
                    request_hash TEXT,
                    cache_key TEXT,
                    request_payload TEXT NOT NULL,
                    response_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(llm_requests)"
                ).fetchall()
            }
            migrations = {
                "trace_id": "ALTER TABLE llm_requests ADD COLUMN trace_id TEXT",
                "latency_ms": (
                    "ALTER TABLE llm_requests ADD COLUMN latency_ms INTEGER"
                ),
                "provider_status_code": (
                    "ALTER TABLE llm_requests "
                    "ADD COLUMN provider_status_code INTEGER"
                ),
                "fallback_used": (
                    "ALTER TABLE llm_requests "
                    "ADD COLUMN fallback_used INTEGER NOT NULL DEFAULT 0"
                ),
                "idempotency_key": (
                    "ALTER TABLE llm_requests ADD COLUMN idempotency_key TEXT"
                ),
                "request_hash": (
                    "ALTER TABLE llm_requests ADD COLUMN request_hash TEXT"
                ),
                "cache_key": "ALTER TABLE llm_requests ADD COLUMN cache_key TEXT",
            }
            for column, statement in migrations.items():
                if column not in existing_columns:
                    connection.execute(statement)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_llm_requests_provider_model
                ON llm_requests(provider, model)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_llm_requests_status
                ON llm_requests(status)
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_llm_requests_idempotency
                ON llm_requests(endpoint, idempotency_key)
                WHERE idempotency_key IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_llm_requests_cache_key
                ON llm_requests(cache_key)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    endpoint TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    request_id TEXT,
                    status TEXT NOT NULL,
                    response_payload TEXT,
                    error TEXT,
                    expires_at INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (endpoint, idempotency_key)
                )
                """
            )
            existing_idempotency_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(idempotency_records)"
                ).fetchall()
            }
            if "expires_at" not in existing_idempotency_columns:
                connection.execute(
                    "ALTER TABLE idempotency_records ADD COLUMN expires_at INTEGER"
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_idempotency_records_status
                ON idempotency_records(status)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_idempotency_records_expires_at
                ON idempotency_records(expires_at)
                """
            )

    def _where_clause(
        self,
        filters: RequestHistoryFilters,
    ) -> tuple[str, tuple[Any, ...]]:
        clauses = []
        params = []
        if filters.provider:
            clauses.append("provider = ?")
            params.append(filters.provider)
        if filters.model:
            clauses.append("model = ?")
            params.append(filters.model)
        if filters.status:
            clauses.append("status = ?")
            params.append(filters.status)
        if filters.endpoint:
            clauses.append("endpoint = ?")
            params.append(filters.endpoint)
        if not clauses:
            return "", tuple()
        return "WHERE " + " AND ".join(clauses), tuple(params)

    def _row_to_record(
        self,
        row: sqlite3.Row,
    ) -> tuple[LLMRequest, LLMResponse]:
        request = self._request_from_dict(json.loads(row["request_payload"]))
        response = self._response_from_dict(json.loads(row["response_payload"]))
        return request, response

    def _request_to_dict(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "request_id": request.request_id,
            "model": request.model,
            "provider": request.provider.value if request.provider else None,
            "messages": [asdict(message) for message in request.messages],
            "input": request.input,
            "stream": request.stream,
            "metadata": request.metadata,
        }

    def _request_from_dict(self, data: dict[str, Any]) -> LLMRequest:
        provider = data.get("provider")
        return LLMRequest(
            request_id=data["request_id"],
            model=data.get("model"),
            provider=ProviderName.from_value(provider) if provider else None,
            messages=[
                LLMMessage(
                    role=message["role"],
                    content=message["content"],
                )
                for message in data.get("messages", [])
            ],
            input=data.get("input"),
            stream=data.get("stream", False),
            metadata=data.get("metadata", {}),
        )

    def _response_to_dict(self, response: LLMResponse) -> dict[str, Any]:
        return {
            "request_id": response.request_id,
            "provider": response.provider.value,
            "model": response.model,
            "status": response.status,
            "content": response.content,
            "embeddings": response.embeddings,
            "usage": asdict(response.usage),
            "error": response.error,
            "trace_id": response.trace_id,
            "provider_status_code": response.provider_status_code,
            "fallback_used": response.fallback_used,
            "fallback_from_provider": (
                response.fallback_from_provider.value
                if response.fallback_from_provider
                else None
            ),
            "fallback_from_model": response.fallback_from_model,
            "latency_ms": response.latency_ms,
            "error_type": response.error_type,
            "raw": response.raw,
        }

    def _response_from_dict(self, data: dict[str, Any]) -> LLMResponse:
        return LLMResponse(
            request_id=data["request_id"],
            provider=ProviderName.from_value(data["provider"]),
            model=data["model"],
            status=data["status"],
            content=data.get("content"),
            embeddings=data.get("embeddings"),
            usage=TokenUsage(**data.get("usage", {})),
            error=data.get("error"),
            trace_id=data.get("trace_id"),
            provider_status_code=data.get("provider_status_code"),
            fallback_used=data.get("fallback_used", False),
            fallback_from_provider=(
                ProviderName.from_value(data["fallback_from_provider"])
                if data.get("fallback_from_provider")
                else None
            ),
            fallback_from_model=data.get("fallback_from_model"),
            latency_ms=data.get("latency_ms"),
            error_type=data.get("error_type"),
            raw=data.get("raw", {}),
        )
