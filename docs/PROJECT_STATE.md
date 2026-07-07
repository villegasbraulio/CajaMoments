# Project State

- **Last verified date:** 2026-07-07
- **Last verified commit:** `635ac11` plus uncommitted Event 360/payment-link implementation updates
- **Default/current branch:** `eventos`
- **Current active work:** Material UI one-column operational backoffice, dialog-based forms, public event/graduation payment pages, Vite vendor chunk splitting, graduation ticket price validity ranges, and Event 360 implemented in working tree; pending commit if desired
- **Known failing checks:** none from checks below

## Architecture snapshot

- **Application type:** Django REST API plus React/Vite single-page admin app.
- **Frontend:** React/Vite SPA in `frontend/src/App.jsx` using Material UI shell/shared controls, dialog-based operational forms, one-column top-level operational layouts, and remaining Bootstrap grid utilities for inner form/table composition.
- **Backend:** `backend/cashflow/` models, serializers, services, viewsets, APIViews, admin, tests.
- **Database:** SQLite locally; Render/PostgreSQL supported by `dj-database-url`.
- **Authentication/authorization:** DRF token/session auth by default; authenticated users can read, `is_staff` users can mutate operational resources; Mercado Pago webhook endpoint is `AllowAny` and signature-gated by settings.
- **External integrations:** Mercado Pago Checkout Pro for event-budget, public event, and graduation-ticket payments; approved payments create idempotent income cash movements; refunds/chargebacks create one idempotent expense reversal when an income movement exists.
- **Audit:** central `AuditLogEntry` records operational create/update/delete and business payment/close actions.
- **Background processing:** none.
- **Deployment/infrastructure:** Render blueprint includes Django API, PostgreSQL, and static React frontend; production payment webhooks require public HTTPS `BACKEND_URL`.

## Important paths

| Purpose | Path |
|---|---|
| Backend/API | `backend/cashflow/` |
| Settings | `backend/config/settings.py` |
| Migrations | `backend/cashflow/migrations/` |
| Tests | `backend/cashflow/tests.py` |
| Frontend | `frontend/src/App.jsx` |
| Documentation | `docs/` |
| Local backend env | `backend/.env` (ignored; loaded by `backend/config/settings.py`) |
| Event receipt PDFs | `backend/cashflow/services.py` (`build_cash_movement_receipt_pdf`) |
| Audit log | `backend/cashflow/models.py` (`AuditLogEntry`) and `/api/audit-log/` |
| Public event payments | `/pagar-evento/{token}` frontend and `/api/event-payments/{token}/` backend |
| Material UI shell | `frontend/src/App.jsx` theme/drawer/snackbar/shared controls |

## Canonical commands

| Action | Command | Last verified |
|---|---|---|
| Backend focused tests | `.venv/bin/python backend/manage.py test cashflow` | 2026-07-07 pass, 33 tests |
| Backend full test suite | `../.venv/bin/python manage.py test` from `backend/` | 2026-07-07 pass, 33 tests |
| Migration drift check | `.venv/bin/python backend/manage.py makemigrations --check --dry-run` | 2026-07-07 pass |
| Frontend build | `npm run build` from `frontend/` | 2026-07-07 pass |
| Deploy settings check | `env DEBUG=False SECRET_KEY=prod-like-secret-key-with-enough-length-for-django-checks ALLOWED_HOSTS=caja-moments-api.onrender.com CORS_ALLOWED_ORIGINS=https://caja-moments-web.onrender.com CSRF_TRUSTED_ORIGINS=https://caja-moments-web.onrender.com SECURE_SSL_REDIRECT=True .venv/bin/python backend/manage.py check --deploy` | 2026-06-29 pass |

## Current constraints

- Do not discard unrelated uncommitted changes.
- Real Mercado Pago checkout needs `MERCADOPAGO_ACCESS_TOKEN`; production webhooks should set `MERCADOPAGO_WEBHOOK_SECRET`, public `BACKEND_URL`, `FRONTEND_URL`, and ideally `MERCADOPAGO_COLLECTOR_ID`.
- Local development loads ignored `backend/.env` before Django settings; real process environment variables still take precedence.
- Approved budget payments post income to account `MERCADOPAGO_ACCOUNT_NAME`, default `MERCADO PAGO`.
- Graduation ticket summary email uses Django `EMAIL_*` settings; local dev defaults to console email backend.
- Graduation ticket prices are staff-loaded in `GraduationTicketPrice`; no cron updates prices.
- Graduation ticket prices use `valid_from` and optional `valid_until`; current ticket price is the latest range containing the payment date.
- Event base amount is stored as the non-optional budget item `Evento`; optionals are budget items with `is_optional=True`.
- Public event payment links expose customer-safe payment context only; staff operations remain authenticated.
- Operational writes require `is_staff`; non-staff authenticated users are read-only.

## Open decisions and unconfirmed assumptions

- See [ADR-0003](adr/0003-auto-record-approved-budget-payments.md): approved online budget payments create one confirmed income `CashMovement` in the Mercado Pago account.
- See [ADR-0004](adr/0004-staff-only-operational-mutations.md): operational writes require staff.
- See [ADR-0005](adr/0005-reverse-refunded-budget-payments.md): refunds and chargebacks create one expense reversal when income exists.
- See [ADR-0006](adr/0006-event-cost-and-operational-details.md): event cost comes from `EventBudget.total()`, and cronograma/funciones are text fields.
- See [ADR-0008](adr/0008-graduation-ticket-pricing-limits-and-close.md): graduation ticket sales use monthly price history, max per graduate, manual payments, and final close/export.
- See [ADR-0009](adr/0009-central-audit-log.md): operational traceability uses a central audit log.
- See [ADR-0010](adr/0010-event-360-and-client-payment-links.md): event totals use base budget item plus optionals, with public payment links and event close snapshots.
- See [ADR-0011](adr/0011-graduation-ticket-price-validity-ranges.md): graduation ticket prices use explicit validity ranges.
- See [ADR-0012](adr/0012-material-ui-backoffice-shell.md): frontend shell/shared controls use Material UI.

## Known issues and technical debt

- Mercado Pago sandbox/live checkout and refund payload date fields still need real end-to-end validation.
- Graduation ticket checkout/webhook still needs sandbox validation before production use.
- Event public checkout/webhook still needs sandbox validation before production use.
- TODO: send employee payment receipt PDFs automatically to `Employee.email` after registering an employee payment; UI/backend only record the email and TODO for now.
- TODO: define legal/fiscal receipt requirements; current event/cash receipts are internal printable PDFs.
- Event close stores final snapshots but does not yet hard-lock every related budget/provider/staff/cash edit.
- Audit entries store concise action summaries, not full before/after field diffs.
- Frontend still loads Bootstrap CDN for existing grid utility classes; remove once remaining layout utilities are migrated to MUI.
- Operational screens use one-column list/detail/actions with dialogs for primary create/edit/pay flows.
- `npm audit --omit=dev` reports Vite/esbuild dev-server advisories; automatic fix requires a breaking Vite major upgrade.
- Vite splits React, Material UI, and vendor chunks; main app chunk is no longer above 500 KB.

## Last completed meaningful work

- **Date:** 2026-07-07
- **Summary:** Completed Material UI list/detail/action UX pass across Caja, Cuentas, Transferencias, Proveedores, Eventos, Egresados, Personal, and Impuestos; added one-column top-level layout and Vite vendor chunk splitting.
- **Worklog:** [2026-07](worklog/2026-07.md)
- **Relevant ADRs:** [ADR-0002](adr/0002-mercadopago-for-event-budget-payments.md), [ADR-0003](adr/0003-auto-record-approved-budget-payments.md), [ADR-0004](adr/0004-staff-only-operational-mutations.md), [ADR-0005](adr/0005-reverse-refunded-budget-payments.md), [ADR-0006](adr/0006-event-cost-and-operational-details.md), [ADR-0008](adr/0008-graduation-ticket-pricing-limits-and-close.md), [ADR-0009](adr/0009-central-audit-log.md), [ADR-0010](adr/0010-event-360-and-client-payment-links.md), [ADR-0011](adr/0011-graduation-ticket-price-validity-ranges.md), [ADR-0012](adr/0012-material-ui-backoffice-shell.md)
