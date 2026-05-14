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

Replay a completed non-streaming response with an idempotency key:

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
