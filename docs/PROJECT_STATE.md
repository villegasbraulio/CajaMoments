# Project State

- **Last verified date:** 2026-07-07
- **Last verified commit:** `2a4e393` (`update mp`) plus uncommitted README/project-memory and event/graduation implementation updates
- **Default/current branch:** `eventos`
- **Current active work:** event operational detail, item-level payments, receipt PDFs, and graduation ticket sales implemented in working tree; pending commit if desired
- **Known failing checks:** none from checks below

## Architecture snapshot

- **Application type:** Django REST API plus React/Vite single-page admin app.
- **Frontend:** `frontend/src/App.jsx` with Bootstrap-style operational screens.
- **Backend:** `backend/cashflow/` models, serializers, services, viewsets, APIViews, admin, tests.
- **Database:** SQLite locally; Render/PostgreSQL supported by `dj-database-url`.
- **Authentication/authorization:** DRF token/session auth by default; authenticated users can read, `is_staff` users can mutate operational resources; Mercado Pago webhook endpoint is `AllowAny` and signature-gated by settings.
- **External integrations:** Mercado Pago Checkout Pro for event-budget and graduation-ticket payments; approved payments create idempotent income cash movements; refunds/chargebacks create one idempotent expense reversal when an income movement exists.
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
| Event receipt PDFs | `backend/cashflow/services.py` (`build_cash_movement_receipt_pdf`) |

## Canonical commands

| Action | Command | Last verified |
|---|---|---|
| Backend focused tests | `.venv/bin/python backend/manage.py test cashflow` | 2026-07-07 pass, 26 tests |
| Backend full test suite | `../.venv/bin/python manage.py test` from `backend/` | 2026-07-07 pass, 26 tests |
| Migration drift check | `.venv/bin/python backend/manage.py makemigrations --check --dry-run` | 2026-07-07 pass |
| Frontend build | `npm run build` from `frontend/` | 2026-07-07 pass |
| Deploy settings check | `env DEBUG=False SECRET_KEY=prod-like-secret-key-with-enough-length-for-django-checks ALLOWED_HOSTS=caja-moments-api.onrender.com CORS_ALLOWED_ORIGINS=https://caja-moments-web.onrender.com CSRF_TRUSTED_ORIGINS=https://caja-moments-web.onrender.com SECURE_SSL_REDIRECT=True .venv/bin/python backend/manage.py check --deploy` | 2026-06-29 pass |

## Current constraints

- Do not discard unrelated uncommitted changes.
- Real Mercado Pago checkout needs `MERCADOPAGO_ACCESS_TOKEN`; production webhooks should set `MERCADOPAGO_WEBHOOK_SECRET`, public `BACKEND_URL`, `FRONTEND_URL`, and ideally `MERCADOPAGO_COLLECTOR_ID`.
- Approved budget payments post income to account `MERCADOPAGO_ACCOUNT_NAME`, default `MERCADO PAGO`.
- Graduation ticket summary email uses Django `EMAIL_*` settings; local dev defaults to console email backend.
- Operational writes require `is_staff`; non-staff authenticated users are read-only.

## Open decisions and unconfirmed assumptions

- See [ADR-0003](adr/0003-auto-record-approved-budget-payments.md): approved online budget payments create one confirmed income `CashMovement` in the Mercado Pago account.
- See [ADR-0004](adr/0004-staff-only-operational-mutations.md): operational writes require staff.
- See [ADR-0005](adr/0005-reverse-refunded-budget-payments.md): refunds and chargebacks create one expense reversal when income exists.
- See [ADR-0006](adr/0006-event-cost-and-operational-details.md): event cost comes from `EventBudget.total()`, and cronograma/funciones are text fields.
- See [ADR-0007](adr/0007-graduation-ticket-sales.md): graduation ticket sales use a linked event, closed graduate list, public token, and Mercado Pago checkout.

## Known issues and technical debt

- Mercado Pago sandbox/live checkout and refund payload date fields still need real end-to-end validation.
- Graduation ticket checkout/webhook still needs sandbox validation before production use.

## Last completed meaningful work

- **Date:** 2026-07-07
- **Summary:** Added event operational detail fields, item-level event payments, movement receipt PDFs, and the public graduation-ticket checkout module with Mercado Pago and email summary.
- **Worklog:** [2026-07](worklog/2026-07.md)
- **Relevant ADRs:** [ADR-0002](adr/0002-mercadopago-for-event-budget-payments.md), [ADR-0003](adr/0003-auto-record-approved-budget-payments.md), [ADR-0004](adr/0004-staff-only-operational-mutations.md), [ADR-0005](adr/0005-reverse-refunded-budget-payments.md), [ADR-0006](adr/0006-event-cost-and-operational-details.md), [ADR-0007](adr/0007-graduation-ticket-sales.md)
