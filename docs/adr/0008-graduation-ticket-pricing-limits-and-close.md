# ADR-0008 - Graduation ticket pricing, limits, and close

- **Date:** 2026-07-07
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** [ADR-0007](0007-graduation-ticket-sales.md)
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/models.py`, `backend/cashflow/services.py`, `backend/cashflow/views.py`, `frontend/src/App.jsx`

## Context

The ticket-sale flow now needs monthly prices, staff-loaded manual ticket payments, per-graduate maximum tickets, and a manual final close that freezes the graduation list.

## Decision

Keep `GraduationEvent` linked to a normal `Event`, but resolve ticket price from `GraduationTicketPrice(valid_from, price)`. Staff loads the price for each month; the system applies the latest `valid_from` not after the requested date. No cron changes prices automatically. `GraduationEvent.max_tickets_per_graduate` caps accumulated purchases/assignments per graduate. Staff can register manual paid ticket purchases; public Mercado Pago payments and manual payments both create `CashMovement`. Closing a graduation event sets `closed_at`, disables the public sale, blocks new graduates and new purchases, and exposes CSV export for the final list.

## Rationale

Staff-loaded monthly prices are the smallest reliable model: no scheduler, no hidden automatic business rule, and historical prices are still queryable. The per-graduate cap belongs on `GraduationEvent` because it is an event-specific sale policy.

## Alternatives considered

- **Automatic monthly cron:** rejected for now because no pricing formula was defined.
- **Single fixed price only:** superseded because it cannot answer historical monthly pricing.
- **Separate ticket ledger:** rejected because `TicketPurchase` plus `CashMovement` already records purchase and cash impact.

## Consequences and tradeoffs

- Staff must create the next month price row before it takes effect.
- Pending public purchases count toward the per-graduate cap, so abandoned checkouts can temporarily consume capacity.
- CSV export is intentionally simple because the salon uses the final list manually.

## Assumptions

- **Confirmed:** the user required monthly price history, per-graduate cap, manual assignment/payment, cash movement creation, and manual close/export.
- **Confirmed:** `CashMovement` remains the source of truth for money.
- **Unconfirmed:** whether pending abandoned checkouts should expire automatically.

## Evidence and references

- `GraduationTicketPrice`, `GraduationEvent.max_tickets_per_graduate`, `TicketPurchase.created_by`, and close/export services.
- Backend tests for price resolution, cap validation, manual payment, close, and audit.

## Follow-up actions

- [ ] Add expiry/release for stale pending public purchases if abandoned checkouts become common.
