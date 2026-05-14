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
Historical metrics are stored as SQLite events in the same database configured
by `SQLITE_DATABASE_PATH`, then aggregated when `/metrics` is read. These metric
events expire after `METRIC_EVENTS_TTL_SECONDS`, which defaults to `604800`.
`llm_active_requests` is intentionally not persisted because it represents the
current process only.

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

Show first-token and generation timing metrics:

```bash
curl -sS http://localhost:8000/metrics \
  | grep -E 'llm_first_token_latency_seconds|llm_generation_duration_seconds'
```

Show cold-start detections:

```bash
curl -sS http://localhost:8000/metrics \
  | grep llm_cold_start_detected_total
```

`llm_request_duration_seconds` tracks total gateway request latency and is also
rendered as a Prometheus histogram with `_bucket`, `_count`, and `_sum` series.
`llm_first_token_latency_seconds` and `llm_generation_duration_seconds` are
also rendered as histograms when the gateway can observe a first token,
currently for streaming chat completions. Non-streaming provider APIs return
only a complete response, so there is no real first-token event to measure at
the gateway boundary.
`llm_cold_start_detected_total` increments when observed first-token latency is
greater than or equal to `COLD_START_FIRST_TOKEN_THRESHOLD_SECONDS`, which
defaults to `5`.

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
