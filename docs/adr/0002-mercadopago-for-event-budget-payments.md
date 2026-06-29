# ADR-0002 — Use Mercado Pago for event budget payments

- **Date:** 2026-06-28
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/`, `backend/config/settings.py`, `backend/requirements.txt`, `frontend/src/App.jsx`, deployment environment variables

## Context

Stage 3 needed online payment for event budgets. The user explicitly allowed taking the Mercado Pago integration from `/Users/braulio/La-Abeja`, which already has Checkout Pro preference creation, webhook logging, signature checks, and payment-state synchronization patterns.

## Decision

Use Mercado Pago Checkout Pro for event-budget collection. Caja Moments will store one local `EventBudgetPayment` attempt per payable budget amount, create preferences through the official Mercado Pago SDK pinned as `mercadopago==3.1.1`, receive payment webhooks through a public unauthenticated endpoint, deduplicate webhook deliveries, validate webhook signatures when required, and mark the budget `APPROVED` only after an approved payment matches local reference, amount, and currency.

## Rationale

This reuses the smallest proven part of the La Abeja flow without importing the whole order/fulfillment model. A redirect URL is enough for this stage, so the frontend does not need the Mercado Pago React SDK. The reference repo pins `mercadopago==3.2.0`, but the local Python 3.9 environment resolved only up to `3.1.1`; that version exposes the required `RequestOptions` API.

## Alternatives considered

- **Embed Mercado Pago Wallet in React:** deferred because redirect checkout covers the requirement with less frontend dependency and state.
- **Create cash movements automatically on approval:** deferred because the receiving account and reconciliation policy are not defined yet.
- **Hand-roll Mercado Pago HTTP calls:** rejected because the reference repo already uses the official SDK and request options for idempotency.

## Consequences and tradeoffs

### Positive

- Local audit trail for payment attempts and webhooks.
- Webhook replay safety through a deduplication key.
- Approved payments cannot approve a budget when amount, currency, or local reference mismatch.

### Negative or limiting

- Deployment must provide Mercado Pago credentials and public HTTPS `BACKEND_URL` for real webhooks.
- Approved payments do not yet create an income `CashMovement`; reconciliation remains manual.

## Assumptions

- **Confirmed:** the user wants Mercado Pago integration and allowed reuse from `/Users/braulio/La-Abeja`.
- **Confirmed:** existing Stage 2 budgets are the payable object for Stage 3.
- **Unconfirmed:** production `MERCADOPAGO_COLLECTOR_ID`, access token, webhook secret, public backend URL, and frontend URL values.

## Evidence and references

- User request on 2026-06-28: continue Stage 3 and use the Mercado Pago integration from `braulio/la-abeja`.
- `/Users/braulio/La-Abeja/backend/apps/payments/`: reference implementation for preference creation, webhook deduplication, signature validation, and sync.
- `backend/cashflow/tests.py`: Stage 3 tests for preference creation, approved sync, and invalid webhook signatures.
- `.venv/bin/pip install -r backend/requirements.txt`: `mercadopago==3.2.0` unavailable for this environment; `3.1.1` installed successfully.

## Follow-up actions

- [ ] Configure `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`, `BACKEND_URL`, `FRONTEND_URL`, and ideally `MERCADOPAGO_COLLECTOR_ID` in production.
- [x] Decide whether approved online payments should generate an income `CashMovement`; see [ADR-0003](0003-auto-record-approved-budget-payments.md).
