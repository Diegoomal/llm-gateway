# DeepInfra

`DeepInfra` is a cloud inference provider for open-source models with API-based access.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `DeepInfra` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`DeepInfra` can be configured as an external provider for the gateway.

Example:

```env
DEEPINFRA_BASE_URL=https://api.deepinfra.com/v1/openai
DEEPINFRA_API_KEY=your-deepinfra-api-key
DEEPINFRA_DEFAULT_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

This configuration allows the gateway to send requests to the `DeepInfra` API.

## Run

DeepInfra does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `DeepInfra` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> DeepInfra Adapter
    -> DeepInfra API
    -> Hosted Model
```

## Chat Completion Example

Example request:

```bash
curl $DEEPINFRA_BASE_URL/chat/completions \
  -H "Authorization: Bearer $DEEPINFRA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `DeepInfra` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "deepinfra",
  "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
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

`DeepInfra` is useful when the project needs access to models outside the local
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

[docs](https://deepinfra.com/docs)
