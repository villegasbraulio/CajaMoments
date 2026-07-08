# Architecture Decision Records

One file per durable architectural or significant technical decision.

## Status meanings

- `proposed`: under consideration or based on an unconfirmed assumption.
- `accepted`: confirmed by user instruction, repository evidence, or external authority.
- `superseded`: replaced by a newer ADR; retained for history.
- `rejected`: considered but intentionally not adopted.

## Decision provenance

Use one or more labels:

- `USER_INSTRUCTION`
- `REPOSITORY_EVIDENCE`
- `EXTERNAL_AUTHORITY`
- `AGENT_ASSUMPTION`

A decision based only on an unconfirmed `AGENT_ASSUMPTION` cannot be `accepted`.

## Index

| ID | Decision | Status | Source | Date | Superseded by |
|---|---|---|---|---|---|
| [ADR-0001](0001-agent-memory-and-decision-records.md) | Maintain persistent agent memory and decision provenance | accepted | USER_INSTRUCTION | 2026-06-25 | — |
| [ADR-0002](0002-mercadopago-for-event-budget-payments.md) | Use Mercado Pago for event budget payments | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-06-28 | — |
| [ADR-0003](0003-auto-record-approved-budget-payments.md) | Auto-record approved budget payments as cash movements | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-06-28 | — |
| [ADR-0004](0004-staff-only-operational-mutations.md) | Staff-only operational mutations | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-06-29 | — |
| [ADR-0005](0005-reverse-refunded-budget-payments.md) | Reverse refunded budget payments | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE, AGENT_ASSUMPTION | 2026-06-29 | — |
| [ADR-0006](0006-event-cost-and-operational-details.md) | Event cost and operational details | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | — |
| [ADR-0007](0007-graduation-ticket-sales.md) | Graduation ticket sales | superseded | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | ADR-0008 |
| [ADR-0008](0008-graduation-ticket-pricing-limits-and-close.md) | Graduation ticket pricing, limits, and close | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | — |
| [ADR-0009](0009-central-audit-log.md) | Central audit log | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | — |
| [ADR-0010](0010-event-360-and-client-payment-links.md) | Event 360 and client payment links | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | — |
| [ADR-0011](0011-graduation-ticket-price-validity-ranges.md) | Graduation ticket price validity ranges | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | — |
| [ADR-0012](0012-material-ui-backoffice-shell.md) | Material UI backoffice shell | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-07 | — |
| [ADR-0013](0013-cash-movement-receipt-emails.md) | Cash movement receipt emails | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-08 | — |
| [ADR-0014](0014-parametrized-event-types.md) | Parametrized event types | accepted | USER_INSTRUCTION, REPOSITORY_EVIDENCE | 2026-07-08 | — |

## Creating an ADR

1. Copy `TEMPLATE.md`.
2. Use the next sequential four-digit ID.
3. Name it `NNNN-short-kebab-case-title.md`.
4. Keep it focused on one durable decision.
5. Add or update its row in this index.
6. Link superseded and replacement ADRs in both directions.
