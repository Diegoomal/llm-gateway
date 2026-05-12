from dataclasses import dataclass

from domain.provider_name import ProviderName


@dataclass(frozen=True)
class ModelRoute:
    provider: ProviderName
    model: str
    fallback_provider: ProviderName | None = None
    fallback_model: str | None = None
