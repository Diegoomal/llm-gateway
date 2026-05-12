from domain.llm_request import LLMRequest
from domain.model_route import ModelRoute
from domain.provider_name import ProviderName


class RoutingService:
    def __init__(
        self,
        default_provider: ProviderName,
        default_models: dict[ProviderName, str],
        fallback_provider: ProviderName | None = None,
        fallback_model: str | None = None,
    ):
        self.default_provider = default_provider
        self.default_models = default_models
        self.fallback_provider = fallback_provider
        self.fallback_model = fallback_model

    def route(self, request: LLMRequest) -> ModelRoute:
        provider = request.provider or self.default_provider
        model = request.model or self.default_models[provider]
        fallback_provider = self._fallback_for(provider)
        fallback_model = (
            self.fallback_model or self.default_models[fallback_provider]
            if fallback_provider is not None
            else None
        )

        return ModelRoute(
            provider=provider,
            model=model,
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
        )

    def _fallback_for(self, provider: ProviderName) -> ProviderName | None:
        if self.fallback_provider and self.fallback_provider != provider:
            return self.fallback_provider

        for candidate in self.default_models:
            if candidate != provider:
                return candidate

        return None
