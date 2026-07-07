# ADR-0003 — Auto-record approved budget payments as cash movements

- **Date:** 2026-06-28
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/`, `backend/config/settings.py`, `frontend/src/App.jsx`

## Context

Stage 3 created Mercado Pago preferences and synchronized payment status, but approved payments still required manual cash reconciliation. Stage 4 needed to close that loop without building a larger accounting workflow.

## Decision

When an `EventBudgetPayment` is synchronized as `approved`, Caja Moments creates exactly one confirmed income `CashMovement` linked to that payment. The movement uses:

- account name from `MERCADOPAGO_ACCOUNT_NAME`, defaulting to `MERCADO PAGO`;
- movement code `COBRO_EVENTO`;
- the payment amount and currency;
- the related budget event;
- payment method `Mercado Pago`.

If the configured account does not exist, it is created as an ARS wallet account. The payment keeps a one-to-one `cash_movement` link so webhook retries do not duplicate income.

## Rationale

The repository already seeds `MERCADO PAGO` as a wallet account and `COBRO_EVENTO` as an event income code. Reusing those is smaller and clearer than introducing a new reconciliation model. The one-to-one link gives deterministic idempotency at the local persistence boundary.

## Alternatives considered

- **Manual reconciliation only:** rejected because the user asked to do the remaining Stage 4 work.
- **Configurable account picker per payment:** deferred because a single environment-configurable Mercado Pago account covers the current flow with less UI and fewer failure paths.
- **Separate ledger table for online collections:** rejected for now because `CashMovement` is already the source of truth for confirmed income.

## Consequences and tradeoffs

### Positive

- Approved online payments immediately affect caja reports and event financial summaries.
- Webhook retries are idempotent through `EventBudgetPayment.cash_movement`.
- The default account matches existing seed data.

### Negative or limiting

- Multi-account Mercado Pago settlement is not modeled yet.
- If the target account/day is closed, movement creation raises validation instead of silently mutating a closed caja day.

## Assumptions

- **Confirmed:** after Stage 3, the user asked to "hace todo", including the suggested Stage 4 automatic cash movement.
- **Confirmed:** repository seed data includes `MERCADO PAGO` and `COBRO_EVENTO`.
- **Unconfirmed:** whether production wants a different account name; configure `MERCADOPAGO_ACCOUNT_NAME` if needed.

## Evidence and references

- `backend/cashflow/management/commands/seed_initial_data.py`: existing Mercado Pago account and event income code.
- `backend/cashflow/tests.py`: approved payment sync creates one cash movement even when called twice.

## Follow-up actions

- [ ] Configure `MERCADOPAGO_ACCOUNT_NAME` in production only if the settlement account name differs from `MERCADO PAGO`.
