# ADR-0009 - Central audit log

- **Date:** 2026-07-07
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/models.py`, `backend/cashflow/services.py`, `backend/cashflow/views.py`, `frontend/src/App.jsx`

## Context

The app already stored `created_by`/`updated_by` on `CashMovement`, but the user requested traceability for operational actions across providers, employees, events, budgets, graduation tickets, closes, payments, and status changes.

## Decision

Add `AuditLogEntry` as a central append-only audit table with `user`, `action`, `model_name`, `object_id`, `detail`, and timestamp. Standard model viewsets log create/update/delete through a shared mixin. Business services log payment, close, void, and final-list actions explicitly. Expose `/api/audit-log/` and a frontend audit screen searchable by user, action, model, object, and detail.

## Rationale

A central log is smaller and easier to query than adding audit fields to every model. Keeping explicit service logs for business actions preserves useful action names such as `provider_payment` and `graduation_close`.

## Alternatives considered

- **Add `created_by`/`updated_by` to every table:** deferred because it adds many columns but still does not describe business actions.
- **Middleware-only logging:** rejected because it cannot reliably name domain actions.

## Consequences and tradeoffs

- The log stores a concise action summary, not a full field diff.
- Public unauthenticated Mercado Pago webhooks can create cash effects without a user; those remain traceable through payment/webhook records and nullable audit users where explicitly logged.

## Assumptions

- **Confirmed:** the user requested at least user, action, model, object id, timestamp, and query exposure.
- **Unconfirmed:** whether future compliance needs full before/after diffs.

## Evidence and references

- `AuditLogEntry` model and `/api/audit-log/`.
- Backend tests asserting user-linked audit entries for service payments and manual ticket payments.

## Follow-up actions

- [ ] Add full field diffs only if audit review requires before/after values.
