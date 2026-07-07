# ADR-0007 - Graduation ticket sales

- **Date:** 2026-07-07
- **Status:** superseded
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** [ADR-0008](0008-graduation-ticket-pricing-limits-and-close.md)
- **Affected areas:** `backend/cashflow/models.py`, `backend/cashflow/services.py`, `backend/cashflow/views.py`, `frontend/src/App.jsx`

## Context

The user requested a public no-login flow for selling graduation-event tickets through Mercado Pago, with staff-managed graduates, emailed summary before checkout, webhook confirmation, cash movement creation, and refund/chargeback reversal.

## Decision

Add a dedicated graduation ticket submodule: `GraduationEvent` links one public ticket sale to one existing `Event`, `Graduate` stores the staff-preloaded closed list, and `TicketPurchase` stores each checkout attempt. A graduate can buy more than once. Email is contact data per purchase, not the unique buyer identity. Approved purchases create one confirmed income `CashMovement` in the configured Mercado Pago account. Refunds and chargebacks create one expense reversal.

## Rationale

Reusing `Event` keeps operations and reporting tied to the canonical event while avoiding flags that would leak ticket-specific fields into every event. A closed graduate list matches the requested name-search flow. Reusing the existing Mercado Pago service pattern keeps webhook validation, idempotency, and cash reconciliation consistent with event-budget payments.

## Alternatives considered

- **Use only `Event` with a type flag:** rejected because ticket price, public token, and capacity are specific to this sale flow.
- **Use email as the buyer identity:** rejected because the requested search starts from the graduate list.
- **Disallow multiple purchases per graduate:** deferred; no business rule was provided.

## Consequences and tradeoffs

- Staff must preload graduates before sharing the public link.
- Multiple purchases by the same graduate are allowed unless a future rule adds a cap.
- Capacity checks count paid purchases only, so pending abandoned checkouts do not reserve seats.

## Assumptions

- **Confirmed:** public checkout must be `AllowAny` and use the existing Mercado Pago pattern.
- **Confirmed:** `CashMovement` remains the cash source of truth.
- **Unconfirmed:** whether production needs per-graduate purchase limits.

## Evidence and references

- Existing Mercado Pago event-budget flow in ADR-0002, ADR-0003, and ADR-0005.
- `GraduationTicketTests` in `backend/cashflow/tests.py`.

## Follow-up actions

- [ ] Add per-graduate or per-purchase caps only when the business defines the rule.
- [ ] Validate the new ticket webhook with a real Mercado Pago sandbox payment before production use.
