# ADR-0014: Parametrized Event Types

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE

## Context

`Event.event_type` was free text, so the same business category could be saved as `Boda`, `Casamiento`, `Cumple`, `Social`, or any other string. The user requested fixed event types: cumpleaños de 15, egresados, evento privado, and casamiento. Egresados also needs to be selectable from the Egresados menu.

## Decision

Use `Event.Type` choices for `event_type`:

- `QUINCE`: Cumpleaños de 15
- `EGRESADOS`: Egresados
- `EVENTO_PRIVADO`: Evento privado
- `CASAMIENTO`: Casamiento

Normalize legacy values in migration `0011_parametrize_event_type`. The Egresados workflow only accepts base events whose type is `EGRESADOS`.

## Rationale

Fixed choices keep filters, reports, and the Egresados module consistent without adding a separate event-type table. The current requested list is short and stable enough for enum choices.

## Alternatives

- Add an editable event-type model: rejected for now because the requested list is fixed.
- Keep frontend-only options: rejected because the API would still accept arbitrary strings.

## Consequences

- API writes now validate `event_type` against the fixed choices.
- Existing legacy values are mapped to the closest supported type, with unknown values becoming `EVENTO_PRIVADO`.
- Egresados links cannot be created from non-Egresados events.

## Affected Areas

- `backend/cashflow/models.py`
- `backend/cashflow/migrations/0011_parametrize_event_type.py`
- `backend/cashflow/serializers.py`
- `frontend/src/App.jsx`

## Assumptions

- **Confirmed:** the canonical event types are the four requested by the user.
- **Confirmed by repository evidence:** `GraduationEvent` already links one-to-one to `Event`, so filtering by base event type is enough.

## Evidence and References

- User instruction on 2026-07-08.
- Existing `Event.event_type` field and `GraduationEvent.event` relation.
- Automated tests in `backend/cashflow/tests.py`.

## Follow-up Actions

- Add a separate event-type model only if the business needs user-managed categories later.
