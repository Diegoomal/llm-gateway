# Perfect Day Automated Test Protocol

This protocol validates the expected "perfect day" flow for the LLM Gateway:
the service starts cleanly, local providers are reachable, OpenAI-like endpoints
work, SQLite stores request history, metrics are emitted, and automated checks
pass.

Use this as the acceptance script before considering a local delivery ready.

## Scope

The protocol covers:

- static checks and unit tests;
- FastAPI application startup;
- health endpoint;
- model listing endpoint;
- chat completion endpoint;
- embeddings endpoint;
- metrics endpoint;
- SQLite persistence;
- Docker Compose configuration when Docker is available.

The protocol does not cover:

- authentication;
- billing;
- multi-tenancy;
- Kubernetes;
- production monitoring.

## Preconditions

Expected tools:

- Python 3.10;
- `make`;
- `curl`;
- `sqlite3`;
- Ollama running locally;
- llama.cpp / llama-server running locally, if fallback or llama.cpp routing is
  part of the test;
- Docker, only for the Docker Compose section.

Expected environment:

```bash
export APP_NAME=llm-gateway
export APP_ENV=local
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_DEFAULT_MODEL=llama3.2:1b
export LLAMA_CPP_BASE_URL=http://localhost:8080
export LLAMA_CPP_DEFAULT_MODEL=local-gguf-model
export DEFAULT_PROVIDER=ollama
export DEFAULT_TIMEOUT_SECONDS=60
export SQLITE_DATABASE_PATH=data/perfect_day.sqlite3
export FALLBACK_PROVIDER=ollama
export FALLBACK_MODEL=llama3.1:latest
```

Start providers before running the gateway:

```bash
ollama serve
ollama pull llama3.2:1b
```

For llama.cpp, start `llama-server` with a local GGUF model and expose the
OpenAI-like API at:

```text
http://localhost:8080
```

## Pass Criteria

The perfect day passes when:

- `make check` succeeds;
- `GET /health` returns `status: ok`;
- `GET /v1/models` returns at least one model from an available provider;
- `POST /v1/chat/completions` returns a non-empty assistant message;
- `POST /v1/embeddings` returns at least one embedding vector;
- `GET /metrics` includes `llm_requests_total`;
- SQLite contains persisted rows in `llm_requests`;
- Docker Compose config validates, when Docker is available.

Instruction-following is evaluated separately from technical success. A chat
request can return HTTP 200 and still receive `PASS_WITH_WARNING` when the
model response is non-empty but differs from the exact expected content.

## Automated Protocol

Run from the repository root.

### 1. Clean Test Database

```bash
rm -f data/perfect_day.sqlite3
mkdir -p data
```

Expected result:

```text
data/perfect_day.sqlite3 does not exist before startup.
```

### 2. Static Checks And Unit Tests

```bash
make check
```

Expected result:

```text
flake8 src tests
pytest
...
passed
```

### 3. Provider Readiness

Check Ollama:

```bash
curl -fsS "$OLLAMA_BASE_URL/api/tags"
```

Expected result:

```text
HTTP 2xx response with available Ollama models.
```

Check llama.cpp when it is part of the test:

```bash
curl -fsS "$LLAMA_CPP_BASE_URL/v1/models"
```

Expected result:

```text
HTTP 2xx response with available llama.cpp models.
```

If llama.cpp is not running, the happy path can still pass for Ollama-only
testing, but fallback behavior is not validated.

### 4. Start Gateway

Start the API:

```bash
make run
```

In another terminal, wait until health is ready:

```bash
curl -fsS http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "app": "llm-gateway",
  "env": "local"
}
```

### 5. List Models

```bash
curl -fsS http://localhost:8000/v1/models
```

Expected result:

```text
Response object is "list" and data contains at least one model.
```

### 6. Chat Completion

```bash
curl -fsS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Reply with exactly: perfect day"
      }
    ]
  }'
```

Expected result:

```text
Response contains:
- object: chat.completion
- provider: ollama
- model: llama3.2:1b
- choices[0].message.content is not empty
- error is null
```

Exact content classification:

```text
PASS: choices[0].message.content.strip() == "perfect day"
PASS_WITH_WARNING: content is non-empty but different from "perfect day"
FAIL: content is empty or the endpoint returns an error
```

### 7. Embeddings

```bash
curl -fsS http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "input": "perfect day"
  }'
```

Expected result:

```text
Response contains:
- object: list
- provider: ollama
- data has at least one item
- data[0].embedding is a numeric vector
- error is null
```

### 8. Metrics

```bash
curl -fsS http://localhost:8000/metrics
```

Expected result includes:

```text
llm_requests_total
llm_request_duration_seconds
llm_tokens_total
llm_active_requests
```

If a provider error occurred during the protocol, metrics should also include:

```text
llm_provider_errors_total
```

### 9. SQLite Persistence

Inspect the database:

```bash
sqlite3 "$SQLITE_DATABASE_PATH" \
  "SELECT request_id, provider, model, status, endpoint, error FROM llm_requests;"
```

Expected result:

```text
At least two rows exist:
- one for /v1/chat/completions
- one for /v1/embeddings
```

Validate row count:

```bash
sqlite3 "$SQLITE_DATABASE_PATH" \
  "SELECT COUNT(*) FROM llm_requests;"
```

Expected result:

```text
2 or greater
```

### 10. Docker Compose Configuration

Run only when Docker is available:

```bash
docker compose config
```

Expected result:

```text
Compose renders successfully and includes the llm-gateway service.
```

Optional container test:

```bash
docker compose up --build
```

Then validate:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/metrics
```

Expected result:

```text
The container starts, health returns ok, and metrics are exposed.
```

## One-Shot Local Script

This script runs the non-Docker protocol against a gateway already started on
port `8000`.

```bash
set -euo pipefail

export SQLITE_DATABASE_PATH="${SQLITE_DATABASE_PATH:-data/perfect_day.sqlite3}"

make check

curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models

curl -fsS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Reply with exactly: perfect day"
      }
    ]
  }'

curl -fsS http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "input": "perfect day"
  }'

curl -fsS http://localhost:8000/metrics | grep llm_requests_total

sqlite3 "$SQLITE_DATABASE_PATH" \
  "SELECT COUNT(*) FROM llm_requests;"
```

## Failure Triage

### Gateway Does Not Start

Run:

```bash
PYTHONPATH=src python3 -c "import main; print(main.app.title)"
```

Expected result:

```text
llm-gateway
```

### Ollama Is Not Reachable

Run:

```bash
curl -v "$OLLAMA_BASE_URL/api/tags"
```

Check whether:

- `ollama serve` is running;
- the configured port is correct;
- the configured model was pulled.

### SQLite Has No Rows

Check whether the gateway process uses the same database path:

```bash
echo "$SQLITE_DATABASE_PATH"
sqlite3 "$SQLITE_DATABASE_PATH" ".tables"
```

The expected table is:

```text
llm_requests
```

### Metrics Are Empty

Submit at least one successful or failed gateway request, then call:

```bash
curl -fsS http://localhost:8000/metrics
```

Metrics are recorded after application service calls finish.
