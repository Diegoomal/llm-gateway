# Ports and Adapters Architecture

This project uses Ports and Adapters Architecture as the primary architectural
style for each bounded-context service.

The central rule is that business rules must not depend on external details.
Domain and application code define the behavior and the required contracts;
adapters implement those contracts for HTTP, messaging, persistence, and other
infrastructure concerns.

## Service Layout

Each service follows the same structure:

- `src/domain`: aggregate roots, value objects, domain events, enums, and domain
  validations.
- `src/application/schemas.py`: command and result objects for use cases.
- `src/application/ports`: interfaces required by the application layer.
- `src/application/services`: use-case orchestration.
- `src/adapters/api`: FastAPI routes and request/response schemas.
- `src/adapters/messaging`: RabbitMQ consumers, event handlers, and publishers.
- `src/adapters/persistence`: SQLite repository implementations.
- `src/configurator.py`: dependency wiring.
- `src/main.py`: HTTP application entrypoint.
- `src/consumer.py`: saga consumer entrypoint when the service consumes events.

## Dependency Direction

Dependencies must point inward:

- `domain` depends on nothing from the application or adapters.
- `application/services` depends on `domain` and `application/ports`.
- `application/ports` defines protocols for repositories, gateways, generators,
  and publishers.
- `adapters` depend on application ports and domain objects.
- `configurator.py` is the composition root and is allowed to instantiate
  concrete adapters.

Do not import adapter implementations from domain or application services.

## Current Bounded Contexts

The repository currently has these service boundaries:

- `account_service`: creates and stores accounts.
- `start_payment_service`: starts payment transactions and publishes
  `payment.started`.
- `debit_account_service`: consumes `payment.started`, debits accounts, and
  publishes debit outcome events.
- `confirm_payment_service`: consumes successful debit events and publishes
  `payment.confirmed`.
- `reverse_payment_service`: handles compensation when debit fails.
- `notify_merchant_service`: consumes `payment.confirmed`, notifies merchants,
  and publishes `merchant.notified`.
- `notify_customer_service`: consumes `payment.confirmed`, notifies customers,
  and publishes `customer.notified`.
- `issue_receipt_service`: consumes `payment.confirmed`, issues receipts, and
  publishes `receipt.issued`.

## Ports

Use ports to describe what the application needs without binding it to a
specific technology.

Examples:

- Repository ports: `AccountRepository`, `TransactionRepository`,
  `NotificationRepository`, `ReceiptRepository`.
- External operation ports: `NotificationGateway`, `ReceiptGenerator`.
- Event ports: `EventPublisher`.
- Driving use-case ports: `ForStartingPayment`, `ForDebitingAccount`,
  `ForConfirmingPayment`, `ForReversingPayment`, `ForNotifyingMerchant`,
  `ForNotifyingCustomer`, `ForIssuingReceipt`.

Application services should receive these ports through their constructors.

## Adapters

Adapters implement ports and translate external representations into
application commands.

Common adapters in this project:

- FastAPI routes translate HTTP requests into command objects.
- RabbitMQ consumers translate event payloads into saga messages.
- Saga event handlers translate saga messages into application commands.
- RabbitMQ publishers translate domain events into JSON payloads and routing
  keys.
- SQLite repositories persist aggregates.
- In-memory adapters support tests and local wiring.

## Saga Events

Services communicate through RabbitMQ topic events. The main saga flow is:

- `payment.started`
- debit outcome events
- `payment.confirmed`
- `merchant.notified`
- `customer.notified`
- `receipt.issued`

Event consumers must be idempotent around the business key for their context:

- notifications: `transaction_id + merchant_id` or `transaction_id + customer_id`
- receipts: `transaction_id`
- payment projections: `transaction_id`

## Implementation Rules

- Keep aggregates independent from entities in other services.
- Store snapshots when a bounded context needs historical data from an event.
- Publish events from application services after successful persistence.
- Do not let notification or receipt failures reverse or cancel payments.
- Do not put RabbitMQ, FastAPI, or SQLite details in domain objects.
- Keep tests focused on domain invariants, use-case behavior, repository
  persistence, API contracts, and messaging contracts.