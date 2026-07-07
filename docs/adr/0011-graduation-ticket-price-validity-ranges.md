# ADR-0011: Graduation Ticket Price Validity Ranges

- **Date:** 2026-07-07
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE

## Context

Graduation ticket prices were stored with `valid_from` only. The user clarified that monthly ticket pricing needs both `vigencia desde` and `vigencia hasta`, and that this monthly price is the event ticket price used by public and manual ticket payments.

## Decision

Add `GraduationTicketPrice.valid_until` as nullable. Resolve the current ticket price by selecting the latest price where `valid_from <= date` and `valid_until` is empty or `valid_until >= date`.

## Rationale

This keeps the existing price-history table and avoids a second pricing model. Nullable `valid_until` supports open-ended current prices.

## Alternatives

- Infer month end from `valid_from`: rejected because the user asked for explicit `hasta`.
- Add a new price-period model: rejected because `GraduationTicketPrice` already represents the concept.

## Consequences

- New migration `0009` adds `valid_until`.
- Admin/API/UI expose both dates.
- Existing prices remain valid because `valid_until` is nullable.

## Affected Areas

- `backend/cashflow/models.py`
- `backend/cashflow/services.py`
- `backend/cashflow/views.py`
- `frontend/src/App.jsx`

## Assumptions

- **Confirmed:** ticket price is the monthly event card price.
- **Unconfirmed:** whether overlapping ranges should be blocked; current behavior picks the latest matching `valid_from`.

## Evidence and References

- User instruction on 2026-07-07.
- Existing `GraduationTicketPrice` table and ticket purchase price resolution.

## Follow-up Actions

- Add overlap validation if operators start entering conflicting ranges.
