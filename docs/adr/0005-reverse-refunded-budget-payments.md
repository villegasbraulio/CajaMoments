# ADR-0005 — Reverse refunded budget payments

- **Date:** 2026-06-29
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE, AGENT_ASSUMPTION
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/services.py`, `backend/cashflow/tests.py`

## Context

Approved Mercado Pago payments already created confirmed income movements. Refunds and chargebacks changed payment status but did not offset the previously recorded income.

## Decision

When a synchronized payment status is `refunded` or `charged_back`, and the payment already has a linked income movement, Caja Moments creates one confirmed expense movement as the reversal. The reversal uses the same account, event, amount, payment method, and a voucher suffix of `-reversal`. Existing reversals are reused so webhook retries do not duplicate expenses.

Approved payment income uses the first available payment date from the Mercado Pago payload: `date_approved`, `money_release_date`, `date_created`, then local date as a fallback.

## Rationale

A counter-movement preserves the immutable caja history and works even if the original payment date is already closed. Voiding the original income would mutate historical cash and can fail after a daily close.

## Alternatives considered

- **Void the original income:** rejected because closed-day rules should remain intact.
- **Add a dedicated reversal relation field:** deferred; voucher-based idempotency is enough for the current flow.
- **Ignore refunds:** rejected because event and caja reports would remain overstated.

## Consequences and tradeoffs

### Positive

- Refunds and chargebacks offset caja results.
- Webhook retries remain idempotent without adding a migration.

### Negative or limiting

- The reversal is linked by voucher/notes, not a dedicated foreign key.
- Payment date field names are inferred from Mercado Pago payload conventions and covered by local tests, but not yet verified in sandbox.

## Assumptions

- **Confirmed:** `CashMovement` is the caja source of truth and closed days must not be mutated.
- **Unconfirmed:** actual sandbox payload date field precedence; if sandbox differs, adjust `_payment_accounting_date`.

## Evidence and references

- `backend/cashflow/services.py`: `ensure_event_budget_payment_reversal` and `_payment_accounting_date`.
- `backend/cashflow/tests.py`: approved payment date and idempotent refund reversal tests.

## Follow-up actions

- [ ] Verify date fields with one Mercado Pago sandbox checkout and refund.
