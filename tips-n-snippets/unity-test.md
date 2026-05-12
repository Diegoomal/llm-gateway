# Pytest - Unit Tests

Unit tests verify small parts of the system in isolation.

In this project, the unit tests focus on the `ForManagingUsers` driving port
behavior implemented by `UserManagementService`.

## Structure

Tests live under:

```text
tests/
```

Example:

```text
tests/test_for_managing_users.py
```

The `pytest.ini` file tells pytest that the source code lives under `src`:

```ini
[pytest]
pythonpath = src
```

With that configuration, imports work normally:

```python
from application.services.user_management_service import UserManagementService
from adapters.persistence.in_memory_user_repository import (
    InMemoryUserRepository,
)
```

## Implemented Tests

The user management tests cover:

- creating a new user successfully;
- preventing a second user with the same email address;
- rejecting invalid email addresses;
- rejecting underage users.

## Run

With the environment active, run:

```bash
pytest
```

Or:

```bash
python3 -m pytest
```

For shorter output:

```bash
pytest -q
```

## Expected Result

When everything is correct, pytest reports passing tests.

If an import error such as `ModuleNotFoundError: No module named 'application'`
appears, check that `pytest.ini` exists at the project root.

[pypi](https://pypi.org/project/pytest/)
