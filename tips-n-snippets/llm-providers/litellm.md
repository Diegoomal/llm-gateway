# LiteLLM

`LiteLLM` is a LLM proxy and SDK for routing requests to multiple model providers with a unified interface.

It allows the project to send LLM requests to a local or external proxy provider, without coupling the
application directly to a specific vendor implementation.

In this project, `LiteLLM` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`LiteLLM` can be configured as an external provider for the gateway.

Example:

```env
LITELLM_BASE_URL=http://localhost:4000
LITELLM_API_KEY=your-litellm-api-key
LITELLM_DEFAULT_MODEL=gpt-4o-mini
```

This configuration allows the gateway to send requests to the `LiteLLM` API.

## Run

Start LiteLLM proxy locally:

```bash
litellm --model gpt-4o-mini --port 4000
```

Run with a configuration file:

```bash
litellm --config ./litellm_config.yaml --port 4000
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `LiteLLM` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> LiteLLM Adapter
    -> LiteLLM Proxy
    -> Configured Provider Model
```

## Chat Completion Example

Example request:

```bash
curl $LITELLM_BASE_URL/chat/completions \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `LiteLLM` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "litellm",
  "model": "gpt-4o-mini",
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

`LiteLLM` is useful when the project needs access to models outside the local
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

[docs](https://docs.litellm.ai/)
