# Hugging Face Inference

`Hugging Face Inference` is a hosted inference provider for models published on Hugging Face.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Hugging Face Inference` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Hugging Face Inference` can be configured as an external provider for the gateway.

Example:

```env
HUGGINGFACE_BASE_URL=https://api-inference.huggingface.co
HUGGINGFACE_API_KEY=your-huggingface-token
HUGGINGFACE_DEFAULT_MODEL=mistralai/Mistral-7B-Instruct-v0.3
```

This configuration allows the gateway to send requests to the `Hugging Face Inference` API.

## Run

Hugging Face Inference does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Hugging Face Inference` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Hugging Face Inference Adapter
    -> Hugging Face Inference API
    -> Hosted Model
```

## Expected Result

When `Hugging Face Inference` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "huggingface",
  "model": "mistralai/Mistral-7B-Instruct-v0.3",
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

`Hugging Face Inference` is useful when the project needs access to models outside the local
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

[docs](https://huggingface.co/docs/api-inference/index)
