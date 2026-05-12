import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from adapters.observability.in_memory_metrics_recorder import (
    InMemoryMetricsRecorder,
)
from adapters.persistence.sqlite_request_repository import (
    SQLiteRequestRepository,
)
from adapters.providers.llama_cpp_provider import LlamaCppProvider
from adapters.providers.ollama_provider import OllamaProvider
from application.ports.for_managing_llm_requests import (
    ForManagingLLMRequests,
)
from application.services.fallback_service import FallbackService
from application.services.llm_gateway_service import LLMGatewayService
from application.services.observability_service import ObservabilityService
from application.services.routing_service import RoutingService
from domain.provider_name import ProviderName


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    ollama_base_url: str
    ollama_default_model: str
    llama_cpp_base_url: str
    llama_cpp_default_model: str
    default_provider: ProviderName
    default_timeout_seconds: int
    sqlite_database_path: str
    fallback_provider: ProviderName | None
    fallback_model: str | None


@dataclass(frozen=True)
class GatewayContainer:
    gateway: ForManagingLLMRequests
    metrics_recorder: InMemoryMetricsRecorder
    settings: Settings


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        app_name=os.getenv("APP_NAME", "llm-gateway"),
        app_env=os.getenv("APP_ENV", "local"),
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434",
        ),
        ollama_default_model=os.getenv(
            "OLLAMA_DEFAULT_MODEL",
            "llama3.2:1b",
        ),
        llama_cpp_base_url=os.getenv(
            "LLAMA_CPP_BASE_URL",
            "http://localhost:8080",
        ),
        llama_cpp_default_model=os.getenv(
            "LLAMA_CPP_DEFAULT_MODEL",
            "local-gguf-model",
        ),
        default_provider=ProviderName.from_value(
            os.getenv("DEFAULT_PROVIDER", "ollama"),
        ),
        default_timeout_seconds=int(
            os.getenv("DEFAULT_TIMEOUT_SECONDS", "60"),
        ),
        sqlite_database_path=os.getenv(
            "SQLITE_DATABASE_PATH",
            "data/llm_gateway.sqlite3",
        ),
        fallback_provider=(
            ProviderName.from_value(os.getenv("FALLBACK_PROVIDER"))
            if os.getenv("FALLBACK_PROVIDER")
            else None
        ),
        fallback_model=os.getenv("FALLBACK_MODEL"),
    )


def configure_gateway_container() -> GatewayContainer:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = load_settings()
    metrics_recorder = InMemoryMetricsRecorder()

    providers = {
        ProviderName.OLLAMA.value: OllamaProvider(
            base_url=settings.ollama_base_url,
            default_model=settings.ollama_default_model,
            timeout_seconds=settings.default_timeout_seconds,
        ),
        ProviderName.LLAMA_CPP.value: LlamaCppProvider(
            base_url=settings.llama_cpp_base_url,
            default_model=settings.llama_cpp_default_model,
            timeout_seconds=settings.default_timeout_seconds,
        ),
    }

    default_models = {
        ProviderName.OLLAMA: settings.ollama_default_model,
        ProviderName.LLAMA_CPP: settings.llama_cpp_default_model,
    }
    fallback_provider = settings.fallback_provider
    if fallback_provider is None:
        fallback_provider = (
            ProviderName.LLAMA_CPP
            if settings.default_provider == ProviderName.OLLAMA
            else ProviderName.OLLAMA
        )

    gateway = LLMGatewayService(
        providers=providers,
        routing_service=RoutingService(
            default_provider=settings.default_provider,
            default_models=default_models,
            fallback_provider=fallback_provider,
            fallback_model=settings.fallback_model,
        ),
        fallback_service=FallbackService(providers),
        observability_service=ObservabilityService(metrics_recorder),
        request_repository=SQLiteRequestRepository(
            settings.sqlite_database_path,
        ),
    )

    return GatewayContainer(
        gateway=gateway,
        metrics_recorder=metrics_recorder,
        settings=settings,
    )


def configure_llm_gateway() -> ForManagingLLMRequests:
    return configure_gateway_container().gateway
