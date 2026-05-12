from collections.abc import Awaitable, Callable
from dataclasses import replace
import asyncio

from application.ports.llm_provider import LLMProvider
from domain.llm_request import LLMRequest
from domain.llm_response import LLMResponse, TokenUsage
from domain.model_route import ModelRoute
from domain.provider_name import ProviderName


ProviderCall = Callable[[LLMProvider, LLMRequest], Awaitable[LLMResponse]]


class FallbackService:
    def __init__(self, providers: dict[str, LLMProvider]):
        self.providers = providers

    async def execute(
        self,
        request: LLMRequest,
        route: ModelRoute,
        provider_call: ProviderCall,
    ) -> LLMResponse:
        try:
            return await self._call_provider(
                request=request,
                provider_name=route.provider.value,
                model=route.model,
                provider_call=provider_call,
            )
        except Exception as primary_error:
            if route.fallback_provider is None or route.fallback_model is None:
                return self._error_response(
                    request=request,
                    provider=route.provider.value,
                    model=route.model,
                    error=primary_error,
                )

            try:
                fallback_response = await self._call_provider(
                    request=request,
                    provider_name=route.fallback_provider.value,
                    model=route.fallback_model,
                    provider_call=provider_call,
                )
                return replace(
                    fallback_response,
                    fallback_used=True,
                    fallback_from_provider=route.provider,
                    fallback_from_model=route.model,
                )
            except Exception as fallback_error:
                return self._error_response(
                    request=request,
                    provider=route.fallback_provider.value,
                    model=route.fallback_model,
                    error=fallback_error,
                )

    async def _call_provider(
        self,
        request: LLMRequest,
        provider_name: str,
        model: str,
        provider_call: ProviderCall,
    ) -> LLMResponse:
        provider = self.providers[provider_name]
        routed_request = replace(request, model=model)
        return await provider_call(provider, routed_request)

    def _error_response(
        self,
        request: LLMRequest,
        provider: str,
        model: str,
        error: Exception,
    ) -> LLMResponse:
        return LLMResponse(
            request_id=request.request_id,
            provider=self._provider_enum(provider),
            model=model,
            status="error",
            usage=TokenUsage(),
            error=str(error),
            error_type=self._error_type(error),
        )

    def _provider_enum(self, provider: str):
        return ProviderName.from_value(provider)

    def _error_type(self, error: Exception) -> str:
        if isinstance(error, TimeoutError):
            return "timeout"
        if isinstance(error, asyncio.TimeoutError):
            return "timeout"
        error_name = error.__class__.__name__.lower()
        if "timeout" in error_name:
            return "timeout"
        if "connect" in error_name:
            return "connection_error"
        if "status" in error_name or "http" in error_name:
            return "provider_http_error"
        return "provider_error"
