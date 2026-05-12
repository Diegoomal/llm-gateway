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
from application.services.routing_service import RoutingService
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse


class LLMGatewayService(ForManagingLLMRequests):
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        routing_service: RoutingService,
        fallback_service: FallbackService,
        observability_service: ObservabilityService,
        request_repository: RequestRepository,
    ):
        self.providers = providers
        self.routing_service = routing_service
        self.fallback_service = fallback_service
        self.observability_service = observability_service
        self.request_repository = request_repository

    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        return await self._execute(
            request=request,
            endpoint="/v1/chat/completions",
            provider_method="chat_completion",
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

    def get_request(
        self,
        request_id: str,
    ) -> tuple[LLMRequest, LLMResponse] | None:
        return self.request_repository.find_by_request_id(request_id)

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
        self.request_repository.save(persisted_request, response)
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
