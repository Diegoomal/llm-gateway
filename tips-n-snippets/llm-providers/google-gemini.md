# Google Gemini

`Google Gemini` is a cloud LLM provider for text, multimodal, and long-context model usage.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Google Gemini` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Google Gemini` can be configured as an external provider for the gateway.

Example:

```env
GEMINI_BASE_URL=https://generativelanguage.googleapis.com
GEMINI_API_KEY=your-gemini-api-key
GEMINI_DEFAULT_MODEL=gemini-1.5-flash
```

This configuration allows the gateway to send requests to the `Google Gemini` API.

## Run

Google Gemini does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Google Gemini` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Google Gemini Adapter
    -> Gemini API
    -> Gemini Model
```

## Expected Result

When `Google Gemini` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "gemini",
  "model": "gemini-1.5-flash",
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

`Google Gemini` is useful when the project needs access to models outside the local
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

[docs](https://ai.google.dev/gemini-api/docs)
