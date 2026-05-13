# OpenRouter

`OpenRouter` is a router provider that exposes many LLMs through a unified API.

It allows the project to send LLM requests to a external routing provider, without coupling the
application directly to a specific vendor implementation.

In this project, `OpenRouter` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`OpenRouter` can be configured as an external provider for the gateway.

Example:

```env
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_DEFAULT_MODEL=openai/gpt-4o-mini
```

This configuration allows the gateway to send requests to the `OpenRouter` API.

## Run

OpenRouter does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `OpenRouter` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> OpenRouter Adapter
    -> OpenRouter API
    -> Selected Provider Model
```

## Chat Completion Example

Example request:

```bash
curl $OPENROUTER_BASE_URL/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `OpenRouter` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "openrouter",
  "model": "openai/gpt-4o-mini",
  "content": "Hello! How can I help you?"
}
```

If the provider configuration is invalid, the gateway may return an error similar to:

```text
Unauthorized: invalid or missing API key
```

If the provider API is unavailable, the gateway may return an error similar to:

```text
Provider unavailable or request timeout
```

## Notes

`OpenRouter` is useful when the project needs access to models outside the local
runtime.

For production-like usage, the project should monitor:

```text
latency
errors
model name
request duration
token usage
rate limits
cost per request
fallback behavior
```

## References

[docs](https://openrouter.ai/docs)
