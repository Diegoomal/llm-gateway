# Fireworks AI

`Fireworks AI` is a cloud inference provider for serving open-source and fine-tuned LLMs.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Fireworks AI` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Fireworks AI` can be configured as an external provider for the gateway.

Example:

```env
FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
FIREWORKS_API_KEY=your-fireworks-api-key
FIREWORKS_DEFAULT_MODEL=accounts/fireworks/models/llama-v3p1-8b-instruct
```

This configuration allows the gateway to send requests to the `Fireworks AI` API.

## Run

Fireworks AI does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Fireworks AI` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Fireworks AI Adapter
    -> Fireworks API
    -> Hosted Model
```

## Chat Completion Example

Example request:

```bash
curl $FIREWORKS_BASE_URL/chat/completions \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `Fireworks AI` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "fireworks",
  "model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
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

`Fireworks AI` is useful when the project needs access to models outside the local
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

[docs](https://docs.fireworks.ai/)
