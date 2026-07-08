# ADR-0015 — Event budget payment purpose

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/models.py`, `backend/cashflow/services.py`, `backend/cashflow/views.py`, `frontend/src/App.jsx`, public event payment API

## Context

Event budget payments need to distinguish business intent: seña, adelanto, or service/optional item. The existing `EventBudgetPayment.payment_type` stores Mercado Pago technical data such as card or transfer type, so reusing it for business categories would mix unrelated concepts.

## Decision

Add `EventBudgetPayment.payment_purpose` with three values:

- `DEPOSIT` for seña.
- `ADVANCE` for adelanto or general event amount.
- `BUDGET_ITEM` for a budget service or optional item.

Approved services already paid are not offered again in the public payment flow and are rejected by backend validation. A registered active seña (`PENDING`, `IN_PROCESS`, or `APPROVED`) blocks another seña; adelantos may be repeated.

## Rationale

Separate purpose keeps Mercado Pago metadata intact, gives accounting code selection a stable domain field, and avoids a free-text comment workflow for a decision that needs validation.

## Alternatives considered

- **Reuse `payment_type`:** rejected because it already represents Mercado Pago payment method type.
- **Free-text payment detail/comment:** rejected because it is harder to validate and report.
- **One generic "other amount" only:** rejected because seña has operational status behavior and duplicate-payment rules.

## Consequences and tradeoffs

### Positive

- Clear reporting and cash movement codes for seña, adelanto, and service payments.
- Backend can block duplicate paid services and duplicate active seña registration.
- Public checkout can hide unavailable concepts instead of relying on user judgment.

### Negative or limiting

- Historical payments without an item or `SEÑA_EVENTO` cash movement are classified as `ADVANCE`.
- The public API adds `can_pay_deposit`, so clients should treat it as part of the event payment contract.

## Assumptions

- **Confirmed:** `payment_type` is preserved for Mercado Pago technical type.
- **Confirmed:** User prefers payment categories over a comment/detail field.
- **Confirmed:** Seña should be registered once while active; adelantos can be multiple.

## Evidence and references

- User instruction on 2026-07-08 to avoid repaying paid services, hide seña when already registered, and split payment types.
- `backend/cashflow/models.py` existing `payment_type` field.
- Focused tests in `backend/cashflow/tests.py`.

## Follow-up actions

- [ ] Validate Mercado Pago sandbox checkout/webhook for all three purposes before production use.
