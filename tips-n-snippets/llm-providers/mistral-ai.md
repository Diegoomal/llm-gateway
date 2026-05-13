# Mistral AI

`Mistral AI` is a cloud LLM provider for Mistral chat, coding, and embedding models.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Mistral AI` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Mistral AI` can be configured as an external provider for the gateway.

Example:

```env
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_API_KEY=your-mistral-api-key
MISTRAL_DEFAULT_MODEL=mistral-small-latest
```

This configuration allows the gateway to send requests to the `Mistral AI` API.

## Run

Mistral AI does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Mistral AI` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Mistral AI Adapter
    -> Mistral API
    -> Mistral Model
```

## Expected Result

When `Mistral AI` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "mistral",
  "model": "mistral-small-latest",
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

`Mistral AI` is useful when the project needs access to models outside the local
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

[docs](https://docs.mistral.ai/)
