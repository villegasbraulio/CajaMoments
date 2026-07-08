# ADR-0013: Cash Movement Receipt Emails

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision source:** USER_INSTRUCTION, REPOSITORY_EVIDENCE

## Context

Cash movements already had an internal printable PDF receipt generated from the confirmed `CashMovement` record and exposed through `/api/cash-movements/{id}/receipt/`. The user requested that every payment or money intake generate a downloadable receipt and that manual and Mercado Pago payments send that receipt by email.

## Decision

Use confirmed `CashMovement` as the receipt source of truth:

- Keep generating receipt PDFs on demand from `CashMovement`.
- Send that PDF by email after the database transaction commits.
- Store `EventBudgetPayment.receipt_email` so public event Mercado Pago payments keep the email entered before the later webhook arrives.
- Infer recipients from explicit payment email first, then related provider, employee, event client, or event contact email.
- Do not fail the payment/cash transaction if SMTP delivery fails; log the delivery failure instead.

## Rationale

The cash movement is already the accounting record and has a stable PDF generator. Reusing it avoids a second receipt ledger and prevents divergent receipt data. `transaction.on_commit` avoids sending receipts for rolled-back operations.

## Alternatives

- Add a separate `Receipt` model: deferred until legal/fiscal receipt requirements are defined.
- Store generated PDFs on disk: rejected for now because receipts are reproducible from the cash movement.
- Send email before transaction commit: rejected because a rollback would leave a false receipt.

## Consequences

- Added migration `0010_eventbudgetpayment_receipt_email`.
- Public event payment creation now requires an email for the receipt.
- Mercado Pago event receipt email uses `EventBudgetPayment.receipt_email`, falling back to Mercado Pago payer email or event contact data.
- Local development uses the configured console email backend; production needs real `EMAIL_*` settings.

## Affected Areas

- `backend/cashflow/models.py`
- `backend/cashflow/migrations/0010_eventbudgetpayment_receipt_email.py`
- `backend/cashflow/services.py`
- `backend/cashflow/views.py`
- `frontend/src/App.jsx`

## Assumptions

- **Confirmed:** receipts remain internal printable PDFs until legal/fiscal requirements are defined.
- **Confirmed:** user wants both manual and Mercado Pago receipts emailed.
- **Confirmed by repository evidence:** confirmed cash movements already provide the receipt PDF and download endpoint.

## Evidence and References

- User instruction on 2026-07-08.
- Existing `build_cash_movement_receipt_pdf()` and `CashMovementViewSet.receipt`.
- Automated tests in `backend/cashflow/tests.py`.

## Follow-up Actions

- Define legal/fiscal receipt requirements before replacing internal PDF receipts.
- Configure production SMTP and validate receipt delivery in the real hosting environment.
