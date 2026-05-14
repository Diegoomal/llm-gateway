import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from adapters.observability.sqlite_metrics_recorder import (
    SQLiteMetricsRecorder,
)
from adapters.persistence.sqlite_request_repository import (
    SQLiteRequestRepository,
)
from adapters.providers.llama_cpp_provider import LlamaCppProvider
from adapters.providers.ollama_provider import OllamaProvider
from application.ports.for_managing_llm_requests import (
    ForManagingLLMRequests,
)
from application.ports.metrics_recorder import MetricsRecorder
from application.services.fallback_service import FallbackService
from application.services.llm_gateway_service import LLMGatewayService
from application.services.observability_service import ObservabilityService
from application.services.provider_concurrency_limiter import (
    ProviderConcurrencyLimiter,
)
from application.services.resilience_service import ResilienceService
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
    provider_max_concurrency: int
    ollama_max_concurrency: int | None
    llama_cpp_max_concurrency: int | None
    rate_limit_enabled: bool
    rate_limit_requests: int
    rate_limit_window_seconds: int
    provider_retry_attempts: int
    provider_retry_base_delay_ms: int
    circuit_breaker_failure_threshold: int
    circuit_breaker_recovery_seconds: int
    idempotency_retry_after_seconds: int
    idempotency_record_ttl_seconds: int
    sqlite_busy_timeout_ms: int
    metric_events_ttl_seconds: int
    cold_start_first_token_threshold_seconds: float


@dataclass(frozen=True)
class GatewayContainer:
    gateway: ForManagingLLMRequests
    metrics_recorder: MetricsRecorder
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
        provider_max_concurrency=int(
            os.getenv("PROVIDER_MAX_CONCURRENCY", "4"),
        ),
        ollama_max_concurrency=_optional_int("OLLAMA_MAX_CONCURRENCY"),
        llama_cpp_max_concurrency=_optional_int("LLAMA_CPP_MAX_CONCURRENCY"),
        rate_limit_enabled=_env_bool("RATE_LIMIT_ENABLED", False),
        rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "60")),
        rate_limit_window_seconds=int(
            os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"),
        ),
        provider_retry_attempts=int(
            os.getenv("PROVIDER_RETRY_ATTEMPTS", "1"),
        ),
        provider_retry_base_delay_ms=int(
            os.getenv("PROVIDER_RETRY_BASE_DELAY_MS", "100"),
        ),
        circuit_breaker_failure_threshold=int(
            os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "0"),
        ),
        circuit_breaker_recovery_seconds=int(
            os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "30"),
        ),
        idempotency_retry_after_seconds=int(
            os.getenv("IDEMPOTENCY_RETRY_AFTER_SECONDS", "1"),
        ),
        idempotency_record_ttl_seconds=int(
            os.getenv("IDEMPOTENCY_RECORD_TTL_SECONDS", "86400"),
        ),
        sqlite_busy_timeout_ms=int(
            os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000"),
        ),
        metric_events_ttl_seconds=int(
            os.getenv("METRIC_EVENTS_TTL_SECONDS", "604800"),
        ),
        cold_start_first_token_threshold_seconds=float(
            os.getenv("COLD_START_FIRST_TOKEN_THRESHOLD_SECONDS", "5"),
        ),
    )


def _optional_int(name: str) -> int | None:
    value = os.getenv(name)
    return int(value) if value else None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def configure_gateway_container() -> GatewayContainer:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = load_settings()
    metrics_recorder = SQLiteMetricsRecorder(
        database_path=settings.sqlite_database_path,
        sqlite_busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        metric_events_ttl_seconds=settings.metric_events_ttl_seconds,
    )

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
        observability_service=ObservabilityService(
            metrics_recorder,
            cold_start_first_token_threshold_seconds=(
                settings.cold_start_first_token_threshold_seconds
            ),
        ),
        request_repository=SQLiteRequestRepository(
            settings.sqlite_database_path,
            idempotency_record_ttl_seconds=(
                settings.idempotency_record_ttl_seconds
            ),
            sqlite_busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        ),
        concurrency_limiter=ProviderConcurrencyLimiter(
            default_limit=settings.provider_max_concurrency,
            provider_limits={
                provider: limit
                for provider, limit in {
                    ProviderName.OLLAMA.value: settings.ollama_max_concurrency,
                    ProviderName.LLAMA_CPP.value: (
                        settings.llama_cpp_max_concurrency
                    ),
                }.items()
                if limit is not None
            },
        ),
        resilience_service=ResilienceService(
            retry_attempts=settings.provider_retry_attempts,
            retry_base_delay_ms=settings.provider_retry_base_delay_ms,
            circuit_breaker_failure_threshold=(
                settings.circuit_breaker_failure_threshold
            ),
            circuit_breaker_recovery_seconds=(
                settings.circuit_breaker_recovery_seconds
            ),
        ),
    )

    return GatewayContainer(
        gateway=gateway,
        metrics_recorder=metrics_recorder,
        settings=settings,
    )


def configure_llm_gateway() -> ForManagingLLMRequests:
    return configure_gateway_container().gateway
