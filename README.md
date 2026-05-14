<!-- AI context: use specs/overview.md as the primary project overview before making code changes. -->
# LLM Gateway

Local-first gateway for managing access to local Large Language Models through
Ollama and llama.cpp / llama-server.

The project follows Hexagonal Architecture with a modular monolith structure.
The domain and application layers define the gateway behavior, while FastAPI,
CLI, Ollama, llama.cpp, persistence, logs, and metrics are implemented as
adapters.

## Goals

- expose one gateway interface for local LLM calls;
- hide provider-specific APIs behind a common provider port;
- standardize requests and responses;
- route requests to Ollama or llama.cpp;
- apply basic fallback when the selected provider fails;
- record structured JSON logs and Prometheus-compatible metrics;
- keep the code easy to extend with future providers.

## Expected Structure

```text
src
├── main.py
├── configurator.py
├── adapters
│   ├── persistence
│   │   └── sqlite_request_repository.py
│   ├── messaging
│   │   └── .gitkeep
│   ├── providers
│   │   ├── ollama_provider.py
│   │   └── llama_cpp_provider.py
│   └── cli
│       └── main.py
├── application
│   ├── services
│   │   ├── llm_gateway_service.py
│   │   ├── routing_service.py
│   │   ├── fallback_service.py
│   │   └── observability_service.py
│   └── ports
│       ├── llm_provider.py
│       ├── request_repository.py
│       ├── metrics_recorder.py
│       └── for_managing_llm_requests.py
└── domain
    ├── llm_request.py
    ├── llm_response.py
    ├── model_route.py
    └── provider_name.py
```

## Environment

Create and activate the Conda environment:

```bash
conda env create -n llm-gateway-env -f env.yml
conda activate llm-gateway-env
```

The gateway is configured with environment variables:

```env
APP_NAME=llm-gateway
APP_ENV=local

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.2:1b

LLAMA_CPP_BASE_URL=http://localhost:8080
LLAMA_CPP_DEFAULT_MODEL=local-gguf-model

DEFAULT_PROVIDER=ollama
DEFAULT_TIMEOUT_SECONDS=60
SQLITE_DATABASE_PATH=data/llm_gateway.sqlite3
SQLITE_BUSY_TIMEOUT_MS=5000
METRIC_EVENTS_TTL_SECONDS=604800
FALLBACK_PROVIDER=ollama
FALLBACK_MODEL=llama3.1:latest

PROVIDER_MAX_CONCURRENCY=4
OLLAMA_MAX_CONCURRENCY=2
LLAMA_CPP_MAX_CONCURRENCY=2

PROVIDER_RETRY_ATTEMPTS=1
PROVIDER_RETRY_BASE_DELAY_MS=100
CIRCUIT_BREAKER_FAILURE_THRESHOLD=0
CIRCUIT_BREAKER_RECOVERY_SECONDS=30

RATE_LIMIT_ENABLED=false
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60

IDEMPOTENCY_RETRY_AFTER_SECONDS=1
IDEMPOTENCY_RECORD_TTL_SECONDS=86400
COLD_START_FIRST_TOKEN_THRESHOLD_SECONDS=5
```

## Commands

- `make run`: runs the application entry point.
- `make test`: runs the test suite.
- `make lint`: checks code style.
- `make docs`: generates the `docs/` directory.
- `make check`: runs lint and tests.

## API Scope

The MVP should expose OpenAI-like endpoints:

```text
POST /v1/chat/completions
POST /v1/embeddings
GET  /v1/models
GET  /health
GET  /metrics
```

`POST /v1/chat/completions` accepts `stream: false` for a complete JSON
response and `stream: true` for OpenAI-compatible server-sent events. Streaming
is normalized for Ollama and llama.cpp/OpenAI-compatible providers and ends with
`data: [DONE]`.

The gateway also supports paginated request history, optional idempotency through
the `Idempotency-Key` header, opt-in non-streaming response cache with
`"cache": true`, provider concurrency limits, retry, circuit breaker, and
optional in-memory rate limiting by API key, authorization header, or IP.

Idempotency is atomic for non-streaming chat completions: the first request
reserves the key before calling the provider, completed requests are replayed,
payload conflicts return `409`, and concurrent duplicates return `425` with a
`Retry-After` header while the first request is still in progress.
Idempotency records expire after `IDEMPOTENCY_RECORD_TTL_SECONDS` to avoid
unbounded growth and allow old keys to be reused after the retention window.
`Idempotency-Key` is currently rejected for streaming requests because replaying
server-sent events safely requires a dedicated persisted event log.

Historical metrics are persisted as SQLite events and rendered as
Prometheus-compatible text from those events, so counters and latency
histograms survive process restarts. `llm_active_requests` remains in memory
because it represents only current runtime state.

## Guides

- [Project overview](specs/overview.md)
- [Project setup](specs/setup.md)
- [Gateway usage commands](specs/gateway-usage-commands.md)
- [Observability commands](specs/observability-commands.md)
- [Perfect day test protocol](specs/perfect-day-test-protocol.md)
- [Ports and Adapters](/tips-n-snippets/ports-and-adapters.md)
- [Unit tests](/tips-n-snippets/unity-test.md)
- [Flake8](/tips-n-snippets/flake8.md)
- [pdoc](/tips-n-snippets/pdoc.md)
- [Makefile](/tips-n-snippets/make.md)

[author](https://github.com/Diegoomal)
