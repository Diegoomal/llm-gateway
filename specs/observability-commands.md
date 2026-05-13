# Observability Commands

This document lists commands for inspecting how the LLM Gateway is being used.

The examples assume the gateway is running at:

```text
http://localhost:8000
```

## Request History

List all recorded requests:

```bash
curl -sS http://localhost:8000/v1/requests | jq
```

Get one request by id:

```bash
curl -sS http://localhost:8000/v1/requests/<request_id> | jq
```

Show a compact request history:

```bash
curl -sS http://localhost:8000/v1/requests \
  | jq '.data[] | {
      request_id,
      provider,
      model,
      endpoint,
      status,
      fallback_used,
      latency_ms
    }'
```

## Token Usage

Show token usage per request:

```bash
curl -sS http://localhost:8000/v1/requests \
  | jq '.data[] | {
      request_id,
      model,
      prompt_tokens: .usage.prompt_tokens,
      completion_tokens: .usage.completion_tokens,
      total_tokens: .usage.total_tokens
    }'
```

Show total token usage across recorded requests:

```bash
curl -sS http://localhost:8000/v1/requests \
  | jq '{
      prompt_tokens: (.data | map(.usage.prompt_tokens) | add),
      completion_tokens: (.data | map(.usage.completion_tokens) | add),
      total_tokens: (.data | map(.usage.total_tokens) | add)
    }'
```

## Failures And Fallback

Show only failed requests:

```bash
curl -sS http://localhost:8000/v1/requests \
  | jq '.data[] | select(.status != "success")'
```

Show requests that used fallback:

```bash
curl -sS http://localhost:8000/v1/requests \
  | jq '.data[] | select(.fallback_used == true)'
```

Show provider errors from metrics:

```bash
curl -sS http://localhost:8000/metrics \
  | grep llm_provider_errors_total
```

## Prometheus Metrics

The `/metrics` endpoint returns Prometheus text format, not JSON.

Show all metrics:

```bash
curl -sS http://localhost:8000/metrics
```

Show request counters:

```bash
curl -sS http://localhost:8000/metrics \
  | grep llm_requests_total
```

Show request duration metrics:

```bash
curl -sS http://localhost:8000/metrics \
  | grep llm_request_duration_seconds
```

Show token metrics:

```bash
curl -sS http://localhost:8000/metrics \
  | grep llm_tokens_total
```

## Current Limitation

The request history endpoint returns request metadata, status, latency, fallback
usage, and token usage. It does not currently expose the original user prompt in
the HTTP response, even though the HTTP adapter stores the raw request payload
in request metadata.
