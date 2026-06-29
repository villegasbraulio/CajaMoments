# Project State

- **Last verified date:** 2026-06-28
- **Last verified commit:** `f635541` plus uncommitted Stage 1-3 event-module work
- **Default/current branch:** `eventos`
- **Current active work:** event operations module through Stage 4: extended event sheet, budgets, Mercado Pago checkout, and automatic cash reconciliation for approved budget payments
- **Known failing checks:** none from focused checks below

## Architecture snapshot

- **Application type:** Django REST API plus React/Vite single-page admin app.
- **Frontend:** `frontend/src/App.jsx` with Bootstrap-style operational screens.
- **Backend:** `backend/cashflow/` models, serializers, services, viewsets, APIViews, admin, tests.
- **Database:** SQLite locally; Render/PostgreSQL supported by `dj-database-url`.
- **Authentication/authorization:** DRF token/session auth by default; Mercado Pago webhook endpoint is `AllowAny` and signature-gated by settings.
- **External integrations:** Mercado Pago Checkout Pro for event-budget payments; approved payments create idempotent income cash movements.
- **Background processing:** none.
- **Deployment/infrastructure:** Render/Vercel files present; production payment webhooks require public HTTPS `BACKEND_URL`.

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
| Migration drift check | `.venv/bin/python backend/manage.py makemigrations --check --dry-run` | 2026-06-28 pass |
| Frontend build | `npm run build` from `frontend/` | 2026-06-28 pass |
| Backend full test suite | `.venv/bin/python backend/manage.py test` | not verified this task |

## Current constraints

- Do not discard existing uncommitted Stage 1-2 event-module changes.
- Real Mercado Pago checkout needs `MERCADOPAGO_ACCESS_TOKEN`; production webhooks should set `MERCADOPAGO_WEBHOOK_SECRET`, public `BACKEND_URL`, `FRONTEND_URL`, and ideally `MERCADOPAGO_COLLECTOR_ID`.
- Approved budget payments post income to account `MERCADOPAGO_ACCOUNT_NAME`, default `MERCADO PAGO`.

## Open decisions and unconfirmed assumptions

- See [ADR-0003](adr/0003-auto-record-approved-budget-payments.md): approved online budget payments create one confirmed income `CashMovement` in the Mercado Pago account.

## Known issues and technical debt

- `docs/PROJECT_STATE.md`, `docs/worklog/`, and event-module files are still uncommitted in this working tree.

## Last completed meaningful work

- **Date:** 2026-06-28
- **Summary:** Added Stage 4 automatic cash movement creation for approved Mercado Pago budget payments, plus a simple cobranzas list.
- **Worklog:** [2026-06](worklog/2026-06.md)
- **Relevant ADRs:** [ADR-0002](adr/0002-mercadopago-for-event-budget-payments.md), [ADR-0003](adr/0003-auto-record-approved-budget-payments.md)
