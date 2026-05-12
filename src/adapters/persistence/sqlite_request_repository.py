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
                    request_payload,
                    response_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    response.provider.value,
                    response.model,
                    response.status,
                    request.metadata.get("endpoint"),
                    response.error,
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
                    request_payload TEXT NOT NULL,
                    response_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
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
            raw=data.get("raw", {}),
        )
