# llama.cpp

`llama.cpp` is a lightweight inference engine for running Large Language Models
locally.

It allows the project to execute LLMs directly from local model files, usually
in `GGUF` format, with good performance and low dependency overhead.

In this project, `llama.cpp` is used to:

```text
run local LLM inference
serve models through llama-server
support OpenAI-compatible chat completions
support local embeddings
act as a provider behind the LLM Gateway
```

## Configuration

`llama.cpp` can be configured as an external provider for the gateway.

Example:

```env
LLAMA_CPP_BASE_URL=http://localhost:8080
LLAMA_CPP_MODEL_PATH=./models/model.gguf
LLAMA_CPP_DEFAULT_MODEL=local-gguf-model
```

This configuration allows the gateway to send requests to the `llama-server`
HTTP API.

## Run

Start `llama-server` with a local model:

```bash
llama-server -m ./models/model.gguf --port 8080
```

Run with a larger context window:

```bash
llama-server -m ./models/model.gguf --port 8080 -c 8192
```

Run with multiple parallel requests:

```bash
llama-server -m ./models/model.gguf --port 8080 -c 16384 -np 4
```

## Usage in the Project

With the environment active:

```bash
make run
```

The application can send requests to `llama.cpp` through the provider adapter.

Example flow:

```text
HTTP Request
    -> LLM Gateway
    -> llama.cpp Adapter
    -> llama-server
    -> Local GGUF Model
```

## Chat Completion Example

Example request:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local-gguf-model",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

## Expected Result

When `llama.cpp` is running correctly, the gateway can send prompts and receive
model responses.

Example response:

```json
{
  "provider": "llama_cpp",
  "model": "local-gguf-model",
  "content": "Hello! How can I help you?"
}
```

If `llama-server` is not running, the gateway may return an error similar to:

```text
Connection refused: http://localhost:8080
```

If the model file is missing or invalid, `llama-server` may fail to start.

## Notes

`llama.cpp` is useful when the project needs more control over local model
execution.

Compared to Ollama, it is usually lower level and more explicit.

For production-like usage, the project should monitor:

```text
latency
errors
model path
model name
request duration
context size
token usage
parallel requests
fallback behavior
```

## References

[github](https://github.com/ggml-org/llama.cpp)