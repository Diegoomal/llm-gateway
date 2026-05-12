# Project Overview

This repository implements a local-first LLM Gateway for managing access to
local Large Language Models through Ollama and llama.cpp / llama-server.

Use this document as the initial context when working with AI coding agents such
as Codex, Claude, or similar tools.

## Goal

The gateway exposes one interface for clients, CLI commands, and future HTTP
adapters. Internally, it chooses a provider, calls the selected local model, and
returns a standardized response.

The main goals are:

- ease of use;
- provider abstraction;
- request and response standardization;
- observability;
- local model execution;
- future extensibility.

## Architecture

The project follows:

- Hexagonal Architecture;
- Modular Monolith;
- Ports and Adapters.

The domain and application layers must not depend directly on Ollama,
llama.cpp, FastAPI, Prometheus, OpenTelemetry, `httpx`, or any external tool.
External integrations must be implemented as adapters.

Expected structure:

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

## Main Flow

```text
Client / CLI / HTTP API
        -> LLM Gateway
        -> Application Service
        -> LLM Provider Port
        -> Ollama or llama.cpp Adapter
        -> Local Model
```

## Domain Layer

The domain layer represents the core concepts of the gateway and must stay
free of external dependencies.

- `src/domain/llm_request.py`: represents chat completion and embedding
  requests, including model, provider preference, messages, input, metadata,
  and `request_id`.
- `src/domain/llm_response.py`: represents standardized provider responses,
  including content, embeddings, usage, provider, model, status, and error.
- `src/domain/model_route.py`: represents provider/model routing decisions.
- `src/domain/provider_name.py`: represents supported provider names such as
  `ollama` and `llama_cpp`.

## Application Ports

Ports define the application boundaries.

- `application/ports/llm_provider.py`: driven port implemented by provider
  adapters. It exposes `chat_completion`, `embeddings`, and `list_models`.
- `application/ports/for_managing_llm_requests.py`: driving port called by CLI,
  HTTP, or future input adapters. It exposes `chat_completion`, `embeddings`,
  and `list_models`.
- `application/ports/request_repository.py`: driven port for request history
  persistence.
- `application/ports/metrics_recorder.py`: driven port for metrics recording
  without coupling the application to Prometheus.

## Application Services

Application services contain orchestration and use-case behavior.

- `llm_gateway_service.py`: implements the `ForManagingLLMRequests` driving
  port. It receives requests, resolves routing, calls providers, records
  history and observability, and returns standardized responses.
- `routing_service.py`: selects provider and model using request preferences
  and configuration defaults.
- `fallback_service.py`: retries through a fallback provider when the primary
  provider fails.
- `observability_service.py`: measures latency, emits structured JSON logs, and
  records metrics through the metrics port.

Services may depend on domain objects and ports, but not on concrete adapters.

## Adapters

Adapters implement external details around the hexagon.

- `adapters/providers/ollama_provider.py`: calls Ollama APIs and translates
  Ollama responses into domain responses.
- `adapters/providers/llama_cpp_provider.py`: calls llama.cpp / llama-server
  OpenAI-like APIs and translates responses into domain responses.
- `adapters/persistence/sqlite_request_repository.py`: stores request history
  in SQLite for local development and durable single-node persistence.
- `adapters/cli/main.py`: exposes basic CLI commands and calls the application
  driving port.
- `adapters/messaging/`: reserved for future event-driven integrations.

HTTP, when implemented, is also an adapter. It should convert HTTP payloads to
domain requests, call `ForManagingLLMRequests`, and convert responses back to
OpenAI-like JSON.

## Configuration

`src/configurator.py` is the composition root. It should load environment
variables and wire concrete adapters into application services.

Expected variables:

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
```

## HTTP API Scope

If HTTP is implemented, expose OpenAI-like endpoints:

```text
POST /v1/chat/completions
POST /v1/embeddings
GET  /v1/models
GET  /health
GET  /metrics
```

The HTTP adapter must not contain routing, fallback, or provider selection
rules.

## Observability

Every request should generate a structured JSON log with:

```text
request_id
provider
model
endpoint
status
latency_ms
error
prompt_tokens
completion_tokens
total_tokens
```

Example:

```json
{
  "request_id": "uuid",
  "provider": "ollama",
  "model": "llama3.2:1b",
  "endpoint": "/v1/chat/completions",
  "status": "success",
  "latency_ms": 1840,
  "prompt_tokens": 120,
  "completion_tokens": 300,
  "total_tokens": 420,
  "error": null
}
```

## Metrics

Expose Prometheus-compatible metrics:

```text
llm_requests_total
llm_request_duration_seconds
llm_provider_errors_total
llm_tokens_total
llm_active_requests
```

Group metrics by:

```text
provider
model
status
endpoint
```

## MVP Scope

Implement the first version with:

- FastAPI;
- `httpx`;
- Ollama adapter;
- llama.cpp adapter;
- structured JSON logs;
- basic metrics endpoint;
- basic routing;
- basic fallback;
- health check;
- SQLite repository;
- CLI adapter.

Out of scope for the MVP:

- authentication;
- multi-tenancy;
- billing;
- advanced cache;
- database persistence;
- distributed queues;
- Kubernetes;
- microservices.

## Tests

Prioritize tests for the application layer because it contains the gateway
behavior.

Recommended coverage:

- routing uses the default provider when no provider is requested;
- explicit provider preference has priority;
- fallback is called when the primary provider fails;
- responses are standardized;
- request history is saved;
- metrics are recorded through the metrics port.

Provider adapters should be tested with mocked HTTP responses.

## Implementation Standards

When changing the project, follow these rules:

- keep the application hexagon directly under `src`;
- keep domain objects pure under `src/domain`;
- define driving and driven ports under `src/application/ports`;
- implement use-case behavior under `src/application/services`;
- keep concrete integrations under `src/adapters`;
- do not import concrete adapters from `domain` or `application/services`;
- wire concrete dependencies in `src/configurator.py`;
- keep provider-specific behavior inside provider adapters;
- keep routing, fallback, and observability orchestration in application
  services;
- add or update tests under `tests/` when behavior changes.

## AI Agent Guidelines

- Before editing, check git status because local uncommitted changes may exist.
- Do not revert existing changes unless explicitly requested.
- Prefer small changes aligned with Ports and Adapters Architecture.
- If creating a new external dependency, define a driven port first.
- If creating a new entry point, call a driving port instead of a concrete
  service method that is not part of a port.
- Run `make test` after behavior changes.
- Run `make lint` or `make check` when changing imports, style, or structure.

## Main Commands

```bash
make run
make test
make lint
make docs
make check
```

See `specs/setup.md` for environment setup and project execution details.
