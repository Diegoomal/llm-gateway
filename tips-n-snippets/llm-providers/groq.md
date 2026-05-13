# Groq

`Groq` is a cloud inference provider focused on fast LLM responses.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Groq` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Groq` can be configured as an external provider for the gateway.

Example:

```env
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_API_KEY=your-groq-api-key
GROQ_DEFAULT_MODEL=llama-3.1-8b-instant
```

This configuration allows the gateway to send requests to the `Groq` API.

## Run

Groq does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Groq` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Groq Adapter
    -> Groq API
    -> Hosted Model
```

## Chat Completion Example

Example request:

```bash
curl $GROQ_BASE_URL/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.1-8b-instant",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `Groq` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "groq",
  "model": "llama-3.1-8b-instant",
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

`Groq` is useful when the project needs access to models outside the local
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

[docs](https://console.groq.com/docs)
