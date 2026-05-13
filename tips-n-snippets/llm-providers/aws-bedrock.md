# AWS Bedrock

`AWS Bedrock` is a managed AWS service for accessing foundation models through AWS infrastructure.

It allows the project to send LLM requests to a external cloud provider, without coupling the
application directly to a specific vendor implementation.

In this project, `AWS Bedrock` is used to:

```text
serve chat completions
support provider abstraction
test external LLM integrations
act as a provider behind the LLM Gateway
```

## Configuration

`AWS Bedrock` can be configured as an external provider for the gateway.

Example:

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
BEDROCK_DEFAULT_MODEL=anthropic.claude-3-haiku-20240307-v1:0
```

This configuration allows the gateway to send requests to the `AWS Bedrock` API.

## Run

Validate AWS credentials and region before running the gateway:

```bash
aws sts get-caller-identity
```

Bedrock does not require a local server. The gateway sends requests to AWS through the provider adapter.


## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `AWS Bedrock` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> AWS Bedrock Adapter
    -> AWS Bedrock Runtime API
    -> Foundation Model
```

## Expected Result

When `AWS Bedrock` is configured correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "aws_bedrock",
  "model": "anthropic.claude-3-haiku-20240307-v1:0",
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

`AWS Bedrock` is useful when the project needs access to models outside the local
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

[docs](https://docs.aws.amazon.com/bedrock/)
