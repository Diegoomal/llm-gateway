from dataclasses import replace

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

    async def _execute(
        self,
        request: LLMRequest,
        endpoint: str,
        provider_method: str,
    ) -> LLMResponse:
        route = self.routing_service.route(request)
        with self.observability_service.track_active_request(route) as timer:
            response = await self.fallback_service.execute(
                request=request,
                route=route,
                provider_call=lambda provider, routed_request: getattr(
                    provider,
                    provider_method,
                )(routed_request),
            )

        persisted_request = replace(
            request,
            metadata={**request.metadata, "endpoint": endpoint},
        )
        self.request_repository.save(persisted_request, response)
        self.observability_service.record(
            response=response,
            endpoint=endpoint,
            duration_seconds=timer.duration_seconds,
        )
        return response
