# Clean Architecture Note

This project now uses Ports and Adapters Architecture as its primary
architectural style.

Clean Architecture and Ports and Adapters share the same dependency principle:
business rules should not depend on external details. In this repository, that
principle is represented with:

- `domain` for pure entities;
- `application/ports` for driving and driven ports;
- `application/services` for application behavior;
- `adapters` for concrete external implementations.

For the current project guide, use:

- [Ports and Adapters](./ports-and-adapters.md)
- [Project overview](../specs/overview.md)
