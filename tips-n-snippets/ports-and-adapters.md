# Ports and Adapters Architecture

Ports and Adapters Architecture, also known as Hexagonal Architecture, keeps the
application core independent from external details.

In this project, the `src` package layout is the application hexagon.
Storage is accessed through a repository port, and the in-memory repository is
only one adapter that implements that port.

## Structure

```text
src/
├── configurator.py
├── main.py
├── domain/
├── application/
│   ├── ports/
│   └── services/
└── adapters/
    ├── cli/
    ├── persistence/
    └── messaging/
```

## Direction Of Dependencies

```text
driving adapter -> application -> driven port <- driven adapter
                         |
                         v
                       domain
```

- `domain` contains pure entities.
- `interfaces/driving_ports` contains operations called by external actors.
- `interfaces/driven_ports` contains resources required by the application.
- `services` implements driving ports.
- `adapters` contains concrete external implementations.

Services must not import concrete adapters.
