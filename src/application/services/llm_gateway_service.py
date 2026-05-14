from collections.abc import AsyncIterator
import asyncio
from dataclasses import asdict, replace
import json
from uuid import uuid4

from application.ports.for_managing_llm_requests import (
    ForManagingLLMRequests,
)
from application.ports.llm_provider import LLMProvider
from application.ports.request_repository import RequestRepository
from application.services.fallback_service import FallbackService
from application.services.observability_service import ObservabilityService
from application.services.provider_concurrency_limiter import (
    ProviderConcurrencyLimiter,
)
from application.services.resilience_service import ResilienceService
from domain.idempotency import IdempotencyReservation
from application.services.routing_service import RoutingService
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, LLMStreamChunk, TokenUsage
from domain.request_history import RequestHistoryFilters, RequestHistoryPage


class LLMGatewayService(ForManagingLLMRequests):
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        routing_service: RoutingService,
        fallback_service: FallbackService,
        observability_service: ObservabilityService,
        request_repository: RequestRepository,
        concurrency_limiter: ProviderConcurrencyLimiter | None = None,
        resilience_service: ResilienceService | None = None,
    ):
        self.providers = providers
        self.routing_service = routing_service
        self.fallback_service = fallback_service
        self.observability_service = observability_service
        self.request_repository = request_repository
        self.concurrency_limiter = concurrency_limiter or (
            ProviderConcurrencyLimiter(default_limit=4)
        )
        self.resilience_service = resilience_service or ResilienceService()

    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        cached_response = await self._cached_response_for(request)
        if cached_response is not None:
            return cached_response
        return await self._execute(
            request=request,
            endpoint="/v1/chat/completions",
            provider_method="chat_completion",
        )

    async def stream_chat_completion(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[LLMStreamChunk]:
        endpoint = "/v1/chat/completions"
        route = self.routing_service.route(request)
        trace_id = request.metadata.get("trace_id") or str(uuid4())
        request_size = self._payload_size(request)
        content_parts: list[str] = []
        final_usage = TokenUsage()
        final_chunk: LLMStreamChunk | None = None
        fallback_used = False
        fallback_from_provider = None
        fallback_from_model = None
        error: str | None = None
        error_type: str | None = None
        status = "success"

        with self.observability_service.track_active_request(route) as timer:
            stream = self._provider_stream(
                request=request,
                provider_name=route.provider.value,
                model=route.model,
            )
            try:
                first_chunk = await anext(stream)
            except StopAsyncIteration:
                first_chunk = LLMStreamChunk(
                    request_id=request.request_id,
                    provider=route.provider,
                    model=route.model,
                    finish_reason="stop",
                )
            except Exception as primary_error:
                if (
                    route.fallback_provider is None
                    or route.fallback_model is None
                ):
                    error = str(primary_error)
                    error_type = self.fallback_service._error_type(
                        primary_error,
                    )
                    status = "error"
                    first_chunk = LLMStreamChunk(
                        request_id=request.request_id,
                        provider=route.provider,
                        model=route.model,
                        finish_reason="error",
                        error=error,
                    )
                    stream = self._empty_stream()
                else:
                    fallback_used = True
                    fallback_from_provider = route.provider
                    fallback_from_model = route.model
                    stream = self._provider_stream(
                        request=request,
                        provider_name=route.fallback_provider.value,
                        model=route.fallback_model,
                    )
                    try:
                        first_chunk = await anext(stream)
                    except Exception as fallback_error:
                        error = str(fallback_error)
                        error_type = self.fallback_service._error_type(
                            fallback_error,
                        )
                        status = "error"
                        first_chunk = LLMStreamChunk(
                            request_id=request.request_id,
                            provider=route.fallback_provider,
                            model=route.fallback_model,
                            finish_reason="error",
                            error=error,
                        )
                        stream = self._empty_stream()

            try:
                async for chunk in self._chain_first(first_chunk, stream):
                    final_chunk = chunk
                    if chunk.content_delta:
                        content_parts.append(chunk.content_delta)
                    if chunk.usage.total_tokens:
                        final_usage = chunk.usage
                    if chunk.error:
                        error = chunk.error
                        status = "error"
                    yield chunk
            except Exception as stream_error:
                error = str(stream_error)
                error_type = self.fallback_service._error_type(stream_error)
                status = "error"
                final_chunk = final_chunk or LLMStreamChunk(
                    request_id=request.request_id,
                    provider=route.provider,
                    model=route.model,
                )
                yield replace(
                    final_chunk,
                    content_delta="",
                    finish_reason="error",
                    error=error,
                )

        latency_ms = round(timer.duration_seconds * 1000)
        response = LLMResponse(
            request_id=request.request_id,
            provider=(
                final_chunk.provider
                if final_chunk is not None
                else route.provider
            ),
            model=final_chunk.model if final_chunk is not None else route.model,
            status=status,
            content="".join(content_parts),
            usage=final_usage,
            error=error,
            trace_id=trace_id,
            provider_status_code=200 if status == "success" else None,
            fallback_used=fallback_used,
            fallback_from_provider=fallback_from_provider,
            fallback_from_model=fallback_from_model,
            latency_ms=latency_ms,
            error_type=error_type,
        )
        response_size = self._payload_size(response)
        persisted_request = replace(
            request,
            metadata={
                **request.metadata,
                "endpoint": endpoint,
                "trace_id": trace_id,
                "request_size": request_size,
            },
        )
        await asyncio.to_thread(
            self.request_repository.save,
            persisted_request,
            response,
        )
        self.observability_service.record(
            response=response,
            endpoint=endpoint,
            duration_seconds=timer.duration_seconds,
            request_size=request_size,
            response_size=response_size,
        )

    async def embeddings(self, request: LLMRequest) -> LLMResponse:
        return await self._execute(
            request=request,
            endpoint="/v1/embeddings",
            provider_method="embeddings",
        )

    async def list_models(self) -> dict[str, list[str]]:
        models = {}
        for provider_name, provider in self.providers.items():
            try:
                models[provider_name] = await provider.list_models()
            except Exception:
                models[provider_name] = []
        return models

    def list_requests(self) -> list[tuple[LLMRequest, LLMResponse]]:
        return self.request_repository.find_all()

    def list_request_page(
        self,
        limit: int,
        offset: int,
        filters: RequestHistoryFilters | None = None,
    ) -> RequestHistoryPage:
        return self.request_repository.find_page(limit, offset, filters)

    def get_request(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        return self.request_repository.find_by_request_id(request_id)

    def get_idempotent_response(
        self,
        endpoint: str,
        idempotency_key: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        return self.request_repository.find_by_idempotency_key(
            endpoint,
            idempotency_key,
        )

    def reserve_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
        request_id: str,
    ) -> IdempotencyReservation:
        return self.request_repository.reserve_idempotency_key(
            endpoint,
            idempotency_key,
            request_hash,
            request_id,
        )

    def complete_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        response: LLMResponse,
    ) -> None:
        self.request_repository.complete_idempotency_key(
            endpoint,
            idempotency_key,
            response,
        )

    def fail_idempotency_key(
        self,
        endpoint: str,
        idempotency_key: str,
        error: str,
    ) -> None:
        self.request_repository.fail_idempotency_key(
            endpoint,
            idempotency_key,
            error,
        )

    async def _execute(
        self,
        request: LLMRequest,
        endpoint: str,
        provider_method: str,
    ) -> LLMResponse:
        route = self.routing_service.route(request)
        trace_id = request.metadata.get("trace_id") or str(uuid4())
        request_size = self._payload_size(request)
        with self.observability_service.track_active_request(route) as timer:
            response = await self.fallback_service.execute(
                request=request,
                route=route,
                provider_call=lambda provider, routed_request: getattr(
                    provider,
                    provider_method,
                )(routed_request),
                call_wrapper=self._call_provider_with_resilience,
            )

        latency_ms = round(timer.duration_seconds * 1000)
        response = replace(
            response,
            trace_id=trace_id,
            latency_ms=latency_ms,
        )
        response_size = self._payload_size(response)
        persisted_request = replace(
            request,
            metadata={
                **request.metadata,
                "endpoint": endpoint,
                "trace_id": trace_id,
                "request_size": request_size,
            },
        )
        await asyncio.to_thread(
            self.request_repository.save,
            persisted_request,
            response,
        )
        self.observability_service.record(
            response=response,
            endpoint=endpoint,
            duration_seconds=timer.duration_seconds,
            request_size=request_size,
            response_size=response_size,
        )
        return response

    def _payload_size(self, payload) -> int:
        return len(json.dumps(asdict(payload), default=str))

    def _provider_stream(
        self,
        request: LLMRequest,
        provider_name: str,
        model: str,
    ) -> AsyncIterator[LLMStreamChunk]:
        provider = self.providers[provider_name]
        routed_request = replace(request, model=model, stream=True)
        return self._limited_provider_stream(
            provider_name,
            model,
            provider.stream_chat_completion(routed_request),
        )

    async def _call_provider_with_resilience(
        self,
        provider_name: str,
        model: str,
        call,
    ):
        async with self.concurrency_limiter.limit(provider_name):
            return await self.resilience_service.execute(
                provider=provider_name,
                model=model,
                call=call,
            )

    async def _limited_provider_stream(
        self,
        provider_name: str,
        model: str,
        stream: AsyncIterator[LLMStreamChunk],
    ) -> AsyncIterator[LLMStreamChunk]:
        async with self.concurrency_limiter.limit(provider_name):
            try:
                async for chunk in stream:
                    yield chunk
                self.resilience_service._record_success((provider_name, model))
            except Exception:
                self.resilience_service._record_failure((provider_name, model))
                raise

    async def _cached_response_for(
        self,
        request: LLMRequest,
    ) -> LLMResponse | None:
        cache_key = request.metadata.get("cache_key")
        if not cache_key:
            return None
        return await asyncio.to_thread(
            self.request_repository.find_cache_entry,
            cache_key,
        )

    async def _chain_first(
        self,
        first_chunk: LLMStreamChunk,
        stream: AsyncIterator[LLMStreamChunk],
    ) -> AsyncIterator[LLMStreamChunk]:
        yield first_chunk
        async for chunk in stream:
            yield chunk

    async def _empty_stream(self) -> AsyncIterator[LLMStreamChunk]:
        if False:
            yield
