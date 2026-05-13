# Anthropic Claude

`Anthropic Claude` is a cloud LLM provider focused on Claude models for chat, reasoning, and coding tasks.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Anthropic Claude` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Anthropic Claude` can be configured as an external provider for the gateway.

Example:

```env
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_KEY=your-anthropic-api-key
ANTHROPIC_DEFAULT_MODEL=claude-3-5-sonnet-latest
```

This configuration allows the gateway to send requests to the `Anthropic Claude` API.

## Run

Anthropic Claude does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Anthropic Claude` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Anthropic Claude Adapter
    -> Anthropic API
    -> Claude Model
```

## Expected Result

When `Anthropic Claude` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-latest",
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

`Anthropic Claude` is useful when the project needs access to models outside the local
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

[docs](https://docs.anthropic.com/)
