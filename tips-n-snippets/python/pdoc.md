# pdoc

`pdoc` generates HTML documentation from Python source code.

It reads modules, classes, functions, signatures, and docstrings, then creates
navigable HTML pages.

In this project, `pdoc` generates documentation for:

```text
configurator
domain
application
adapters
```

## Run

With the environment active:

```bash
make docs
```

This command runs:

```bash
PYTHONPATH=src pdoc configurator domain application adapters -o docs
```

## Why `PYTHONPATH=src` Is Needed

The source code lives under `src`.

The command tells Python to use `src` as the import root for modules such as:

```text
src/configurator.py
src/domain
src/application
src/adapters
```

Without it, `pdoc` may not resolve imports such as:

```python
from application.services.user_management_service import UserManagementService
```

## Expected Result

The command creates:

```text
docs/
```

The main generated page is usually:

```text
docs/index.html
```

## Improving Documentation

`pdoc` is more useful when the code has docstrings.

Example:

```python
class UserManagementService:
    """Manage users through the application driving port."""
```

[pypi](https://pypi.org/project/pdoc/)
