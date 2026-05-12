# Flake8

`flake8` is a linting tool for Python.

It checks style issues, unused imports, invalid names, long lines, and other
details that help keep the project consistent.

In this project, `flake8` checks:

```text
src/
tests/
```

## Configuration

Configuration lives in `.flake8` at the project root:

```ini
[flake8]
max-line-length = 88
extend-ignore = E203
exclude =
    .git,
    .venv,
    __pycache__,
    docs
```

This configuration sets an 88-character line length, ignores generated or
environment directories, and ignores `E203` to avoid conflicts with formatters
such as `black`.

## Run

With the environment active:

```bash
make lint
```

This command runs:

```bash
flake8 src tests
```

## Expected Result

When the code has no lint issues, the command exits without output.

If there is a problem, `flake8` shows the file, line, column, error code, and
message.

Example:

```text
src/main.py:10:1: F401 'os' imported but unused
```

[pypi](https://pypi.org/project/flake8/)
