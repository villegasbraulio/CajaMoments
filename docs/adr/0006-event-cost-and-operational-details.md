# ADR-0006 - Event cost and operational details

- **Date:** 2026-07-07
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE
- **Supersedes:** none
- **Superseded by:** none
- **Affected areas:** `backend/cashflow/models.py`, `backend/cashflow/services.py`, `frontend/src/App.jsx`

## Context

Event detail needed costo, cronograma, croquis, funciones, optional items, item-level payments, and cash receipts. The repository already has `EventBudget`, `EventBudgetItem.is_optional`, `EventStaffAssignment.role`, and `CashMovement` as money source of truth.

## Decision

Use `EventBudget.total()` as the source of truth for event cost instead of adding a second `Event.costo` field. Add operational fields to `Event` for `schedule_notes`, `sketch`, and `function_notes`. Keep staffing assignments as the structured source for assigned employee roles; `function_notes` is free-form operating guidance. Item-level payments reuse `EventBudgetPayment` with optional `budget_item`, and each confirmed payment creates one linked `CashMovement`. Cash receipts are generated as a minimal PDF directly in Python without adding a dependency.

## Rationale

The budget already owns itemized costs and optional totals. Duplicating cost on `Event` would create reconciliation work. Reusing `EventBudgetPayment` avoids a second payment state machine for item payments. A simple receipt PDF covers the current printable/downloadable need without adding ReportLab or WeasyPrint.

## Alternatives considered

- **Add `Event.costo`:** rejected because it duplicates budget totals.
- **Create schedule item and function role tables now:** deferred until repeated structured querying is needed.
- **Add a PDF dependency:** deferred because the current receipt is simple text.

## Consequences and tradeoffs

- Event cost changes when budget items change.
- Cronograma and funciones are searchable/editable text, not structured timelines.
- The PDF is intentionally plain; richer layout will require a rendering dependency later.

## Assumptions

- **Confirmed:** the user asked to decide and document the event-cost source of truth.
- **Confirmed:** repository evidence shows budgets and budget items already calculate event totals.
- **Unconfirmed:** whether future operations need structured schedule blocks.

## Evidence and references

- `EventBudget.subtotal()`, `optional_total()`, and `total()` in `backend/cashflow/models.py`.
- `EventBudgetPayment.budget_item` and item manual/MP payment tests in `backend/cashflow/tests.py`.

## Follow-up actions

- [ ] Add structured schedule items only when the UI needs sorting/filtering by time blocks.
- [ ] Add a richer PDF renderer only when receipt branding/layout requirements exceed plain text.
