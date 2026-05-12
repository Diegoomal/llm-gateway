# Makefile

The `Makefile` centralizes common project commands.

## Available Commands

### Run The Example

```bash
make run
```

Runs:

```bash
PYTHONPATH=src python3 src/main.py
```

### Run Tests

```bash
make test
```

Runs:

```bash
pytest
```

### Run Lint

```bash
make lint
```

Runs:

```bash
flake8 src tests
```

### Generate Documentation

```bash
make docs
```

Runs:

```bash
PYTHONPATH=src pdoc configurator domain application adapters -o docs
```

### Run Main Checks

```bash
make check
```

Runs lint and tests:

```bash
make lint
make test
```

## Recommended Flow

During development:

```bash
make test
```

Before finishing:

```bash
make check
```

To update documentation:

```bash
make docs
```
