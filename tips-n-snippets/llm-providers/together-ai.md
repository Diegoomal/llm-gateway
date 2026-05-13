# Together AI

`Together AI` is a cloud inference provider for open-source LLMs through a hosted API.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Together AI` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Together AI` can be configured as an external provider for the gateway.

Example:

```env
TOGETHER_BASE_URL=https://api.together.xyz/v1
TOGETHER_API_KEY=your-together-api-key
TOGETHER_DEFAULT_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo
```

This configuration allows the gateway to send requests to the `Together AI` API.

## Run

Together AI does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Together AI` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Together AI Adapter
    -> Together API
    -> Hosted Open Model
```

## Chat Completion Example

Example request:

```bash
curl $TOGETHER_BASE_URL/chat/completions \
  -H "Authorization: Bearer $TOGETHER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `Together AI` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "together",
  "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
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

`Together AI` is useful when the project needs access to models outside the local
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

[docs](https://docs.together.ai/)
