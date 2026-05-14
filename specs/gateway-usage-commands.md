# Gateway Usage Commands

This document lists common commands for manually testing the LLM Gateway HTTP
API.

The examples assume the Docker service is running and exposing the gateway at:

```text
http://localhost:8000
```

## Health Check

```bash
curl -sS http://localhost:8000/health | jq
```

Expected response:

```json
{
  "status": "ok",
  "app": "llm-gateway",
  "env": "local"
}
```

## List Models

Show the full response:

```bash
curl -sS http://localhost:8000/v1/models | jq
```

Show only model names:

```bash
curl -sS http://localhost:8000/v1/models \
  | jq -r '.data[].id'
```

Show provider and model name:

```bash
curl -sS http://localhost:8000/v1/models \
  | jq -r '.data[] | "\(.owned_by)\t\(.id)"'
```

## Chat Completion

Send a request to Ollama through the gateway:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }' | jq
```

Show only the assistant answer:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }' | jq -r '.choices[0].message.content'
```

Show answer and token usage:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }' \
  | jq '{
      request_id: .id,
      model,
      provider,
      answer: .choices[0].message.content,
      usage
    }'
```

Stream partial tokens as server-sent events:

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "stream": true,
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }'
```

## Idempotency

Use `Idempotency-Key` on non-streaming chat completions when the client may
retry the same logical request after a timeout, network failure, or process
restart. The key should be unique per logical request and reused only with the
same JSON payload.

First request with a new key:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-request-1" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }' | jq
```

Replay after the first request completed:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-request-1" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }' | jq
```

The gateway returns the persisted response and does not execute the provider a
second time.

If the same key is reused with a different payload, the gateway returns `409`:

```bash
curl -i http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-request-1" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "messages": [
      {
        "role": "user",
        "content": "Payload diferente"
      }
    ]
  }'
```

Concurrent requests using the same `Idempotency-Key` are not executed more than
once. While the first request is still running, duplicates return `425` with
the body `"Request with this Idempotency-Key is still in progress"` and a
`Retry-After` header. Clients should wait at least that number of seconds and
retry with the same key and the exact same payload until they receive the
completed replay or a terminal error. `IDEMPOTENCY_RETRY_AFTER_SECONDS`
controls the header value and defaults to `1`.

Idempotency records are retained for `IDEMPOTENCY_RECORD_TTL_SECONDS`, which
defaults to `86400`. After expiration, the same key can be reserved again as a
new logical request. The SQLite adapter removes expired records opportunistically
when new idempotency keys are reserved.

Streaming requests with `Idempotency-Key` return `400`:

```bash
curl -i -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: stream-request-1" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "stream": true,
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase"
      }
    ]
  }'
```

Streaming idempotency is rejected until the gateway can persist and replay SSE
events exactly. Replaying only the final aggregated text would not reproduce the
same streaming contract for clients.

## Cache

Use opt-in cache for a non-streaming request:

```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "provider": "ollama",
    "cache": true,
    "messages": [
      {
        "role": "user",
        "content": "Responda em uma frase: o que é um gateway de LLM?"
      }
    ]
  }' | jq
```

## Embeddings

Send an embedding request:

```bash
curl -sS http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "all-minilm:latest",
    "provider": "ollama",
    "input": "Texto para gerar embedding"
  }' | jq
```

Show vector dimensions and token usage:

```bash
curl -sS http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "all-minilm:latest",
    "provider": "ollama",
    "input": "Texto para gerar embedding"
  }' \
  | jq '{
      model,
      provider,
      dimensions: (.data[0].embedding | length),
      usage
    }'
```

## Request History

List persisted requests with pagination and filters:

```bash
curl -sS \
  'http://localhost:8000/v1/requests?limit=20&offset=0&provider=ollama' \
  | jq
```

## Provider Requirements

When running with Docker Compose, the gateway calls local providers through
`host.docker.internal`.

For Ollama, make sure the host has Ollama running and the requested model
available:

```bash
ollama serve
ollama pull llama3.2:1b
```
