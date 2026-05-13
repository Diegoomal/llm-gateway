# Azure OpenAI

`Azure OpenAI` is a Azure-hosted provider for OpenAI models deployed inside Azure resources.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `Azure OpenAI` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`Azure OpenAI` can be configured as an external provider for the gateway.

Example:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

This configuration allows the gateway to send requests to the `Azure OpenAI` API.

## Run

Azure OpenAI does not require a local model server.

Configure the environment variables and run the gateway:

```bash
make run
```


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `Azure OpenAI` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Azure OpenAI Adapter
    -> Azure OpenAI API
    -> Azure OpenAI Deployment
```

## Expected Result

When `Azure OpenAI` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "azure_openai",
  "model": "your-deployment-name",
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

`Azure OpenAI` is useful when the project needs access to models outside the local
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

[docs](https://learn.microsoft.com/azure/ai-services/openai/)
