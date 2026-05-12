# Ollama

`Ollama` is a tool for running Large Language Models locally.

It allows the project to execute, manage, and expose local LLMs through a simple
HTTP API, without depending directly on external cloud providers.

In this project, `Ollama` is used to:

```text
run local models
serve chat completions
test LLM integrations locally
support the LLM Gateway provider layer
```

## Configuration

Ollama runs as an external service and can be configured through environment
variables.

Example:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.2:1b
```

This configuration allows the gateway to send requests to the Ollama API.

## Run

Start Ollama locally:

```bash
ollama serve
```

Pull a model:

```bash
ollama pull llama3.2:1b
```

Run a model directly:

```bash
ollama run llama3.2:1b
```

## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to Ollama through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> Ollama Adapter
    -> Ollama API
    -> Local Model
```

## Expected Result

When Ollama is running correctly, the gateway can send prompts and receive model
responses.

Example response:

```json
{
  "provider": "ollama",
  "model": "llama3.2:1b",
  "content": "Hello! How can I help you?"
}
```

If Ollama is not running, the gateway may return an error similar to:

```text
Connection refused: http://localhost:11434
```

## Notes

Ollama is useful for local development, testing, and experimentation with LLMs.

For production-like usage, the project should also monitor:

```text
latency
errors
model name
request duration
token usage
fallback behavior
```

[pypi](https://pypi.org/project/ollama/)