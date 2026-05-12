# Project Setup

This document explains how to prepare the local environment, configure local
LLM providers, run the gateway, and execute checks.

## Requirements

The project uses Python 3.10. The recommended environment is described in
`env.yml` and installs the dependencies listed in `requirements.txt`.

Expected tools:

- Conda or Mamba, recommended;
- Python 3.10, if using a virtual environment without Conda;
- `make`, for the `Makefile` shortcuts;
- Ollama, for the Ollama provider;
- llama.cpp / llama-server, for the llama.cpp provider.

## Option 1: Conda Environment

Create the environment from `env.yml`:

```bash
conda env create -f env.yml
```

Activate the environment defined in `env.yml`:

```bash
conda activate project-env
```

Or create it with the project-specific name:

```bash
conda env create -n llm-gateway-env -f env.yml
conda activate llm-gateway-env
```

## Option 2: `venv` Environment

If you do not want to use Conda, create a virtual environment with Python 3.10:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On some systems, the binary may be named `python`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Configure the gateway with environment variables:

```env
APP_NAME=llm-gateway
APP_ENV=local

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.2:1b

LLAMA_CPP_BASE_URL=http://localhost:8080
LLAMA_CPP_DEFAULT_MODEL=local-gguf-model

DEFAULT_PROVIDER=ollama
DEFAULT_TIMEOUT_SECONDS=60
SQLITE_DATABASE_PATH=data/llm_gateway.sqlite3
```

For local development, these values can be exported in the shell:

```bash
export APP_NAME=llm-gateway
export APP_ENV=local
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_DEFAULT_MODEL=llama3.2:1b
export LLAMA_CPP_BASE_URL=http://localhost:8080
export LLAMA_CPP_DEFAULT_MODEL=local-gguf-model
export DEFAULT_PROVIDER=ollama
export DEFAULT_TIMEOUT_SECONDS=60
export SQLITE_DATABASE_PATH=data/llm_gateway.sqlite3
```

## Local Providers

### Ollama

Start Ollama locally and make sure the configured model is available:

```bash
ollama serve
ollama pull llama3.2:1b
```

The default gateway URL for Ollama is:

```text
http://localhost:11434
```

### llama.cpp / llama-server

Start `llama-server` with a local GGUF model. The exact command depends on the
local installation and model path.

The gateway expects llama.cpp to expose an OpenAI-like API at:

```text
http://localhost:8080
```

## Run The Project

Use the `Makefile` target:

```bash
make run
```

The project entry point is:

```bash
PYTHONPATH=src python3 src/main.py
```

When the HTTP adapter is implemented, the gateway should expose:

```text
POST /v1/chat/completions
POST /v1/embeddings
GET  /v1/models
GET  /health
GET  /metrics
```

## Run Tests

Execute:

```bash
make test
```

Or run `pytest` directly:

```bash
pytest
```

The `pytest.ini` file configures `pythonpath = src`, so manually exporting
`PYTHONPATH` is not necessary for tests.

## Run Lint

Execute:

```bash
make lint
```

This command runs:

```bash
flake8 src tests
```

## Run All Checks

Execute:

```bash
make check
```

This target runs lint and tests:

```bash
make lint
make test
```

## Generate Documentation

Execute:

```bash
make docs
```

This command uses `pdoc` to generate documentation in `docs/`:

```bash
PYTHONPATH=src pdoc configurator domain application adapters -o docs
```

## Expected Structure After Implementation

```text
.
├── env.yml
├── requirements.txt
├── Makefile
├── pytest.ini
├── specs/
│   ├── overview.md
│   └── setup.md
├── src/
│   ├── configurator.py
│   ├── main.py
│   ├── adapters/
│   │   ├── cli/
│   │   ├── messaging/
│   │   ├── persistence/
│   │   └── providers/
│   ├── application/
│   │   ├── ports/
│   │   └── services/
│   └── domain/
└── tests/
```

## Common Issues

### `ModuleNotFoundError` When Running Manually

If you execute Python files without `make`, include `src` in `PYTHONPATH`:

```bash
PYTHONPATH=src python3 src/main.py
```

### Conda Environment Created With An Unexpected Name

The `env.yml` file may define a generic environment name. Confirm which name
was used:

```bash
conda env list
```

### Missing Dependencies

Reinstall dependencies in the active environment:

```bash
pip install -r requirements.txt
```

### Ollama Is Not Reachable

Confirm the Ollama server is running and reachable at `OLLAMA_BASE_URL`:

```bash
curl http://localhost:11434/api/tags
```

### llama.cpp Is Not Reachable

Confirm `llama-server` is running and reachable at `LLAMA_CPP_BASE_URL`:

```bash
curl http://localhost:8080/v1/models
```

## Recommended Development Flow

1. Activate the environment.
2. Start the local provider needed for the test.
3. Make small changes aligned with Ports and Adapters Architecture.
4. Run `make test`.
5. Run `make lint` when changing imports, formatting, or adding files.
6. Use `make check` before finishing a delivery.
