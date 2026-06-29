# Project State

- **Last verified date:** 2026-06-29
- **Last verified commit:** `eventos` plus uncommitted event-module and hardening work
- **Default/current branch:** `eventos`
- **Current active work:** event operations module through Stage 5 hardening: extended event sheet, budgets, Mercado Pago checkout, automatic cash reconciliation, refund reversals, staff-only writes, frontend pagination, and Render frontend blueprint
- **Known failing checks:** none from checks below

## Architecture snapshot

- **Application type:** Django REST API plus React/Vite single-page admin app.
- **Frontend:** `frontend/src/App.jsx` with Bootstrap-style operational screens.
- **Backend:** `backend/cashflow/` models, serializers, services, viewsets, APIViews, admin, tests.
- **Database:** SQLite locally; Render/PostgreSQL supported by `dj-database-url`.
- **Authentication/authorization:** DRF token/session auth by default; authenticated users can read, `is_staff` users can mutate operational resources; Mercado Pago webhook endpoint is `AllowAny` and signature-gated by settings.
- **External integrations:** Mercado Pago Checkout Pro for event-budget payments; approved payments create idempotent income cash movements; refunds/chargebacks create one idempotent expense reversal when an income movement exists.
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

## Canonical commands

| Action | Command | Last verified |
|---|---|---|
| Backend focused tests | `.venv/bin/python backend/manage.py test cashflow` | 2026-06-28 pass |
| Backend full test suite | `../.venv/bin/python manage.py test` from `backend/` | 2026-06-29 pass, 23 tests |
| Migration drift check | `.venv/bin/python backend/manage.py makemigrations --check --dry-run` | 2026-06-29 pass |
| Frontend build | `npm run build` from `frontend/` | 2026-06-29 pass |
| Deploy settings check | `env DEBUG=False SECRET_KEY=prod-like-secret-key-with-enough-length-for-django-checks ALLOWED_HOSTS=caja-moments-api.onrender.com CORS_ALLOWED_ORIGINS=https://caja-moments-web.onrender.com CSRF_TRUSTED_ORIGINS=https://caja-moments-web.onrender.com SECURE_SSL_REDIRECT=True .venv/bin/python backend/manage.py check --deploy` | 2026-06-29 pass |

## Current constraints

- Do not discard existing uncommitted event-module and hardening changes.
- Real Mercado Pago checkout needs `MERCADOPAGO_ACCESS_TOKEN`; production webhooks should set `MERCADOPAGO_WEBHOOK_SECRET`, public `BACKEND_URL`, `FRONTEND_URL`, and ideally `MERCADOPAGO_COLLECTOR_ID`.
- Approved budget payments post income to account `MERCADOPAGO_ACCOUNT_NAME`, default `MERCADO PAGO`.
- Operational writes require `is_staff`; non-staff authenticated users are read-only.

## Open decisions and unconfirmed assumptions

- See [ADR-0003](adr/0003-auto-record-approved-budget-payments.md): approved online budget payments create one confirmed income `CashMovement` in the Mercado Pago account.
- See [ADR-0004](adr/0004-staff-only-operational-mutations.md): operational writes require staff.
- See [ADR-0005](adr/0005-reverse-refunded-budget-payments.md): refunds and chargebacks create one expense reversal when income exists.

## Known issues and technical debt

- Event-module, hardening, docs, and migration files are still uncommitted in this working tree.
- Mercado Pago sandbox/live checkout and refund payload date fields still need real end-to-end validation.

## Last completed meaningful work

- **Date:** 2026-06-29
- **Summary:** Closed audit gaps with local migrations applied, frontend paginated reference loading, staff-only operational writes, Render frontend blueprint, safer env docs, approved-payment accounting dates, and idempotent refund/chargeback reversals.
- **Worklog:** [2026-06](worklog/2026-06.md)
- **Relevant ADRs:** [ADR-0002](adr/0002-mercadopago-for-event-budget-payments.md), [ADR-0003](adr/0003-auto-record-approved-budget-payments.md), [ADR-0004](adr/0004-staff-only-operational-mutations.md), [ADR-0005](adr/0005-reverse-refunded-budget-payments.md)
