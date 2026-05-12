import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from domain.llm_request import LLMMessage, LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.provider_name import ProviderName


class SQLiteRequestRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path
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
                    request_payload,
                    response_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

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
