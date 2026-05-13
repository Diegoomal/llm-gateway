# OpenAI

`OpenAI` is a cloud LLM provider for chat completions, embeddings, and multimodal models.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `OpenAI` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`OpenAI` can be configured as an external provider for the gateway.

Example:

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your-openai-api-key
OPENAI_DEFAULT_MODEL=gpt-4.1-mini
```

This configuration allows the gateway to send requests to the `OpenAI` API.

## Run

OpenAI does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `OpenAI` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> OpenAI Adapter
    -> OpenAI API
    -> OpenAI Model
```

## Chat Completion Example

Example request:

```bash
curl $OPENAI_BASE_URL/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `OpenAI` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "openai",
  "model": "gpt-4.1-mini",
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

`OpenAI` is useful when the project needs access to models outside the local
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

[docs](https://platform.openai.com/docs)
