# ADR-0004 — Staff-only operational mutations

- **Date:** 2026-06-29
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/views.py`, `backend/cashflow/tests.py`, `README.md`

## Context

The API already required authentication, but any authenticated user could create, edit, close, pay, or void operational records. That was enough for a single trusted operator, but too broad once the system is used with more than one account.

## Decision

Operational write actions now require `request.user.is_staff`. Authenticated non-staff users may still read protected API resources. Public endpoints remain limited to login, healthcheck, and the Mercado Pago webhook.

## Rationale

Django already provides `is_staff`; using it avoids a new role model and keeps the rule understandable. This is the smallest useful authorization boundary for the current admin-style app.

## Alternatives considered

- **Custom roles per module:** deferred until there is a real need for caja-only, eventos-only, or read-only named roles.
- **Keep authenticated-write access:** rejected because it leaves no deterministic boundary between consultation and operation.

## Consequences and tradeoffs

### Positive

- Prevents non-staff users from mutating cash, event, provider, employee, tax, and payment resources.
- Reuses Django admin/superuser setup.

### Negative or limiting

- There is still no fine-grained per-module permission model.

## Assumptions

- **Confirmed:** the user asked to close all identified audit gaps.
- **Confirmed:** the README already tells operators to create Django admin/superuser accounts.
- **Unconfirmed:** whether production needs named business roles; if it does, replace `ReadOnlyOrStaff` with a role-aware permission class.

## Evidence and references

- `backend/cashflow/views.py`: `ReadOnlyOrStaff`.
- `backend/cashflow/tests.py`: non-staff mutation is forbidden.
- `README.md`: operational permission note.

## Follow-up actions

- [ ] Add fine-grained roles only when the business names actual user groups and allowed actions.
