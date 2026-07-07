# ADR-0010: Event 360 and Client Payment Links

- **Date:** 2026-07-07
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE

## Context

Caja Moments needs event work to happen from one operational center instead of separate client, event, budget, payment, provider, staff, tax, and audit screens. The user confirmed that most clients are unlikely to repeat, except schools, so client creation should be part of event creation in the main workflow. The user also confirmed that `monto + opcionales` is the final event total, clients may pay seña, optionals, or other event amounts, and client-facing payment links should use Mercado Pago.

The repository already had `Event`, `Client`, `EventBudget`, `EventBudgetItem`, `EventBudgetPayment`, Mercado Pago webhook reconciliation, `CashMovement`, receipts, and `AuditLogEntry`.

## Decision

Use `EventBudget` as the financial source of truth for event totals:

- The event base amount is represented by a non-optional `EventBudgetItem` named `Evento`.
- Optional charges remain `EventBudgetItem.is_optional = True`.
- Event total is `EventBudget.total()`, which equals base amount plus optionals.
- Approved event payments, whether manual or Mercado Pago, create confirmed income `CashMovement` rows linked to the event.
- Event status uses the simple lifecycle `presupuesto`, `señado`, `confirmado`, `realizado`, `cerrado`, and `cancelado`.
- Each event has a public payment token for `/pagar-evento/{token}`.
- Public payment context exposes only customer-safe event totals and payable items.
- Closing an event stores final total, paid, pending, expenses, and result snapshots on `Event`.
- The admin UI centers event operations in Evento 360: client, budget, optionals, payments, providers, staff, cash movements, receipts, and audit history.
- Receipts remain internal printable PDFs for now; legal/fiscal receipt behavior is deferred.

## Rationale

Reusing budgets and payments avoids a second sales ledger. It keeps Mercado Pago reconciliation, cash close, receipts, reports, and event balance on the same accounting path. A public token gives clients a shareable link without exposing the internal admin app.

## Alternatives

- Add a separate event invoice/order model: rejected for now because it duplicates `EventBudget`, `EventBudgetItem`, and `EventBudgetPayment`.
- Keep clients as a required separate setup step: rejected for the main workflow because the user confirmed most clients are event-specific.
- Make legal/fiscal receipts now: deferred because the user asked for internal printable receipts first.

## Consequences

- Existing events get a generated public payment token through migration.
- Event creation in the UI creates a client inline and a base budget item.
- Client API remains available for staff and future repeat-client/school flows, but it is no longer the primary event creation path.
- Event close is a business snapshot; it does not prevent all historical edits yet beyond new direct event payments.

## Affected Areas

- Backend models, migrations, services, serializers, views, and URLs under `backend/cashflow/`.
- Frontend event, public payment, and tax screens in `frontend/src/App.jsx`.
- Mercado Pago budget payment preference back URLs.
- Project tests and documentation.

## Assumptions

- **Confirmed:** client-facing event payments should be Mercado Pago.
- **Confirmed:** event total is base amount plus optionals.
- **Confirmed:** receipts can remain internal printable for now.
- **Unconfirmed:** exact legal/fiscal receipt requirements and provider format.
- **Unconfirmed:** whether event close must become a hard immutable lock for all related records.

## Evidence and References

- User instruction on 2026-07-07.
- Existing ADR-0002 and ADR-0003 for Mercado Pago and cash movement creation.
- Existing repository models `EventBudget`, `EventBudgetItem`, `EventBudgetPayment`, `CashMovement`, and `AuditLogEntry`.

## Follow-up Actions

- Validate event payment checkout/webhook/refund in a real Mercado Pago sandbox before production use.
- Define legal/fiscal receipt requirements before replacing internal printable PDFs.
- Decide whether closed events should hard-block editing budgets, staff, providers, and linked cash movements.
