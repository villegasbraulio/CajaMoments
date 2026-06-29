from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import logging
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date as parse_iso_date, parse_datetime

from .models import (
    Account,
    AccountTransfer,
    CashMovement,
    DailyAccountClose,
    DailyCashCloseGroup,
    Employee,
    EmployeePayment,
    Event,
    EventBudget,
    EventBudgetItem,
    EventBudgetPayment,
    EventStaffAssignment,
    MovementCode,
    Provider,
    ProviderLedgerEntry,
    Reminder,
    TaxPayment,
    TaxType,
)

try:
    import mercadopago
    from mercadopago.config import RequestOptions
except ImportError:
    mercadopago = None
    RequestOptions = None


logger = logging.getLogger(__name__)


def get_code(code):
    return MovementCode.objects.get(code=code)


def ensure_account_day_is_open(account, movement_date):
    is_closed = DailyAccountClose.objects.filter(
        account=account,
        close_group__date=movement_date,
        closed_at__isnull=False,
    ).exists()
    if is_closed:
        raise ValidationError("La cuenta ya esta cerrada para esa fecha.")


def calculate_account_balance(account, up_to_date=None, before_date=None):
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)

    movements = account.cash_movements.filter(status=CashMovement.Status.CONFIRMED)
    if up_to_date:
        movements = movements.filter(date_payment__lte=up_to_date)
    if before_date:
        movements = movements.filter(date_payment__lt=before_date)

    totals = movements.values("movement_type").annotate(total=Sum("amount"))
    balance = account.initial_balance
    for row in totals:
        amount = row["total"] or Decimal("0.00")
        movement_type = row["movement_type"]
        if movement_type in (
            CashMovement.MovementType.INCOME,
            CashMovement.MovementType.TRANSFER_IN,
            CashMovement.MovementType.ADJUSTMENT,
        ):
            balance += amount
        elif movement_type in (
            CashMovement.MovementType.EXPENSE,
            CashMovement.MovementType.TRANSFER_OUT,
        ):
            balance -= amount
    return balance


@transaction.atomic
def confirm_cash_movement(movement, user=None):
    if not isinstance(movement, CashMovement):
        movement = CashMovement.objects.select_for_update().get(pk=movement)
    ensure_account_day_is_open(movement.account, movement.date_payment)
    movement.status = CashMovement.Status.CONFIRMED
    movement.updated_by = user
    movement.save()
    return movement


@transaction.atomic
def void_cash_movement(movement, reason, user=None):
    if not isinstance(movement, CashMovement):
        movement = CashMovement.objects.select_for_update().get(pk=movement)
    ensure_account_day_is_open(movement.account, movement.date_payment)
    if movement.status == CashMovement.Status.VOIDED:
        return movement
    movement.status = CashMovement.Status.VOIDED
    movement.void_reason = reason
    movement.voided_by = user
    movement.updated_by = user
    movement.save()
    return movement


@transaction.atomic
def create_balance_adjustment(account, declared_balance, movement_date=None, description="", user=None):
    if not isinstance(account, Account):
        account = Account.objects.select_for_update().get(pk=account)
    movement_date = movement_date or timezone.localdate()
    ensure_account_day_is_open(account, movement_date)
    declared_balance = Decimal(str(declared_balance))
    current_balance = calculate_account_balance(account, up_to_date=movement_date)
    difference = declared_balance - current_balance
    if difference == 0:
        return None

    code = get_code("AJUSTE_CAJA")
    if difference > 0:
        movement_type = CashMovement.MovementType.ADJUSTMENT
        amount = difference
    else:
        movement_type = CashMovement.MovementType.EXPENSE
        amount = abs(difference)

    return CashMovement.objects.create(
        date_payment=movement_date,
        description=description or f"Ajuste de caja {account.name}",
        movement_type=movement_type,
        amount=amount,
        account=account,
        code=code,
        status=CashMovement.Status.CONFIRMED,
        created_by=user,
        updated_by=user,
    )


@transaction.atomic
def create_account_transfer(
    from_account,
    to_account,
    amount,
    transfer_date=None,
    fee_amount=Decimal("0.00"),
    description="Transferencia entre cuentas",
    user=None,
):
    if not isinstance(from_account, Account):
        from_account = Account.objects.select_for_update().get(pk=from_account)
    if not isinstance(to_account, Account):
        to_account = Account.objects.select_for_update().get(pk=to_account)

    transfer_date = transfer_date or timezone.localdate()
    amount = Decimal(str(amount))
    fee_amount = Decimal(str(fee_amount or "0.00"))
    ensure_account_day_is_open(from_account, transfer_date)
    ensure_account_day_is_open(to_account, transfer_date)

    transfer = AccountTransfer.objects.create(
        date=transfer_date,
        from_account=from_account,
        to_account=to_account,
        amount=amount,
        fee_amount=fee_amount,
        description=description,
        status=AccountTransfer.Status.CONFIRMED,
    )

    transfer_code = get_code("TRANSFERENCIA_INTERNA")
    CashMovement.objects.create(
        date_payment=transfer_date,
        description=description,
        movement_type=CashMovement.MovementType.TRANSFER_OUT,
        amount=amount,
        account=from_account,
        code=transfer_code,
        transfer=transfer,
        status=CashMovement.Status.CONFIRMED,
        created_by=user,
        updated_by=user,
    )
    CashMovement.objects.create(
        date_payment=transfer_date,
        description=description,
        movement_type=CashMovement.MovementType.TRANSFER_IN,
        amount=amount,
        account=to_account,
        code=transfer_code,
        transfer=transfer,
        status=CashMovement.Status.CONFIRMED,
        created_by=user,
        updated_by=user,
    )

    if fee_amount > 0:
        fee_code = MovementCode.objects.filter(code="SERVICIOS").first() or get_code("OTRO_EGRESO")
        CashMovement.objects.create(
            date_payment=transfer_date,
            description=f"Comision - {description}",
            movement_type=CashMovement.MovementType.EXPENSE,
            amount=fee_amount,
            account=from_account,
            code=fee_code,
            transfer=transfer,
            status=CashMovement.Status.CONFIRMED,
            created_by=user,
            updated_by=user,
        )

    return transfer


def _sum_amount(queryset):
    return queryset.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


class MercadoPagoAPIError(Exception):
    pass


class PaymentIntegrityError(Exception):
    pass


class MercadoPagoClient:
    def __init__(self, access_token=None):
        self.access_token = access_token or settings.MERCADOPAGO_ACCESS_TOKEN
        if not self.access_token:
            raise MercadoPagoAPIError("Mercado Pago no esta configurado.")
        if mercadopago is None:
            raise MercadoPagoAPIError("El SDK de Mercado Pago no esta instalado.")
        self.sdk = mercadopago.SDK(self.access_token)

    def create_budget_preference(self, payment):
        budget = payment.budget
        event = budget.event
        payload = {
            "items": [
                {
                    "id": f"event-budget:{budget.id}",
                    "title": f"Presupuesto {event.name}",
                    "description": event.event_type or "Evento",
                    "currency_id": payment.currency,
                    "quantity": 1,
                    "unit_price": float(payment.amount),
                }
            ],
            "external_reference": f"event-budget-payment:{payment.id}",
            "metadata": {
                "event_budget_payment_id": str(payment.id),
                "budget_id": str(budget.id),
                "event_id": str(event.id),
            },
            "payment_methods": {"installments": 6},
        }
        payer = self._build_payer(event)
        if payer:
            payload["payer"] = payer
        notification_url = self._build_notification_url()
        if notification_url:
            payload["notification_url"] = notification_url
        back_urls = self._build_back_urls(payment)
        if back_urls:
            payload["back_urls"] = back_urls
            payload["auto_return"] = "approved"
        request_options = RequestOptions(
            access_token=self.access_token,
            custom_headers={"x-idempotency-key": payment.idempotency_key},
        )
        response = self.sdk.preference().create(payload, request_options)
        return self._unwrap_response(response, "No pudimos crear la preferencia de pago.")

    def get_payment(self, payment_id):
        response = self.sdk.payment().get(payment_id)
        return self._unwrap_response(response, "No pudimos consultar el pago en Mercado Pago.")

    def _build_payer(self, event):
        email = event.contact_email or (event.client.email if event.client_id else "")
        name = event.contact_name or (event.client.name if event.client_id else "")
        if not email and not name:
            return {}
        payer = {}
        if email:
            payer["email"] = email
        if name:
            parts = name.split(maxsplit=1)
            payer["name"] = parts[0]
            if len(parts) > 1:
                payer["surname"] = parts[1]
        return payer

    def _build_back_urls(self, payment):
        frontend_url = _resolve_public_base_url(settings.FRONTEND_URL)
        if not frontend_url:
            return {}
        query = urlencode({"event": payment.budget.event_id, "budget": payment.budget_id})
        return {
            "success": f"{frontend_url}/?payment_status=approved&{query}",
            "failure": f"{frontend_url}/?payment_status=failure&{query}",
            "pending": f"{frontend_url}/?payment_status=pending&{query}",
        }

    def _build_notification_url(self):
        backend_url = _resolve_public_base_url(settings.BACKEND_URL)
        return f"{backend_url}/api/event-budget-payments/webhook/" if backend_url else None

    def _unwrap_response(self, response, fallback_message):
        if not isinstance(response, dict):
            raise MercadoPagoAPIError("Mercado Pago devolvio una respuesta invalida.")
        status_code = response.get("status")
        body = response.get("response")
        if not isinstance(body, dict):
            body = response if "id" in response else {}
        if isinstance(status_code, int) and status_code >= 400:
            raise MercadoPagoAPIError(_extract_mp_error(body, fallback_message))
        if not body or body.get("error"):
            raise MercadoPagoAPIError(_extract_mp_error(body, fallback_message))
        return body


def _resolve_public_base_url(value):
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        return None
    parsed = urlsplit(normalized)
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return None
    if parsed.scheme != "https" or not parsed.netloc:
        logger.warning("mercadopago_public_url_invalid", extra={"value": normalized})
        return None
    return normalized


def _extract_mp_error(body, fallback_message):
    for key in ("message", "error"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    cause = body.get("cause")
    if isinstance(cause, list) and cause and isinstance(cause[0], dict):
        description = cause[0].get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
    return fallback_message


@transaction.atomic
def create_event_budget_payment_preference(budget):
    if not isinstance(budget, EventBudget):
        budget = EventBudget.objects.select_for_update().select_related("event", "event__client").get(pk=budget)
    else:
        budget = EventBudget.objects.select_for_update().select_related("event", "event__client").get(pk=budget.pk)
    amount = budget.total()
    if amount <= 0:
        raise ValidationError("El presupuesto no tiene importe para cobrar.")
    reusable = (
        budget.payments.select_for_update()
        .filter(amount=amount, currency=Account.Currency.ARS, status__in=[EventBudgetPayment.Status.PENDING, EventBudgetPayment.Status.IN_PROCESS])
        .exclude(mp_preference_id="")
        .first()
    )
    payment = reusable or EventBudgetPayment.objects.create(budget=budget, amount=amount, currency=Account.Currency.ARS)
    if not payment.mp_preference_id:
        preference = MercadoPagoClient().create_budget_preference(payment)
        preference_id = str(preference.get("id") or "")
        if not preference_id:
            raise MercadoPagoAPIError("Mercado Pago no devolvio una preferencia valida.")
        payment.mp_preference_id = preference_id
        payment.preference_init_point = str(preference.get("init_point") or "")
        payment.preference_sandbox_init_point = str(preference.get("sandbox_init_point") or "")
        payment.save(
            update_fields=[
                "mp_preference_id",
                "preference_init_point",
                "preference_sandbox_init_point",
                "updated_at",
            ]
        )
    return payment


PAYMENT_STATUS_MAP = {
    "approved": EventBudgetPayment.Status.APPROVED,
    "in_process": EventBudgetPayment.Status.IN_PROCESS,
    "pending": EventBudgetPayment.Status.PENDING,
    "authorized": EventBudgetPayment.Status.PENDING,
    "rejected": EventBudgetPayment.Status.REJECTED,
    "cancelled": EventBudgetPayment.Status.CANCELLED,
    "refunded": EventBudgetPayment.Status.REFUNDED,
    "charged_back": EventBudgetPayment.Status.REFUNDED,
}


@transaction.atomic
def sync_event_budget_payment(payment_id, payment_data):
    payment = EventBudgetPayment.objects.select_for_update().select_related("budget", "budget__event", "cash_movement").get(pk=payment_id)
    _validate_approved_budget_payment(payment, payment_data)
    raw_status = str(payment_data.get("status") or "pending").lower()
    payment.status = PAYMENT_STATUS_MAP.get(raw_status, EventBudgetPayment.Status.PENDING)
    payment.mp_payment_id = str(payment_data.get("id") or payment.mp_payment_id)
    payment.mp_merchant_order_id = str((payment_data.get("order") or {}).get("id") or payment.mp_merchant_order_id)
    payment.status_detail = str(payment_data.get("status_detail") or "")
    payment.payment_method = str(payment_data.get("payment_method_id") or "")
    payment.payment_type = str(payment_data.get("payment_type_id") or "")
    payment.installments = int(payment_data.get("installments") or payment.installments or 1)
    payment.save(
        update_fields=[
            "status",
            "mp_payment_id",
            "mp_merchant_order_id",
            "status_detail",
            "payment_method",
            "payment_type",
            "installments",
            "updated_at",
        ]
    )
    if payment.status == EventBudgetPayment.Status.APPROVED and payment.budget.status != EventBudget.Status.APPROVED:
        payment.budget.status = EventBudget.Status.APPROVED
        payment.budget.save(update_fields=["status", "updated_at"])
    if payment.status == EventBudgetPayment.Status.APPROVED:
        ensure_event_budget_payment_cash_movement(payment, payment_data)
    elif raw_status in {"refunded", "charged_back"}:
        ensure_event_budget_payment_reversal(payment, payment_data)
    return payment


def _payment_accounting_date(payment_data):
    for key in ("date_approved", "money_release_date", "date_created"):
        value = payment_data.get(key)
        if not value:
            continue
        parsed_datetime = parse_datetime(str(value))
        if parsed_datetime:
            if timezone.is_aware(parsed_datetime):
                return timezone.localtime(parsed_datetime).date()
            return parsed_datetime.date()
        parsed_date = parse_iso_date(str(value)[:10])
        if parsed_date:
            return parsed_date
    return timezone.localdate()


def ensure_event_budget_payment_cash_movement(payment, payment_data=None):
    if payment.cash_movement_id:
        return payment.cash_movement
    payment_data = payment_data or {}
    account_name = str(settings.MERCADOPAGO_ACCOUNT_NAME or "MERCADO PAGO").strip() or "MERCADO PAGO"
    account, _ = Account.objects.get_or_create(
        name=account_name,
        defaults={
            "type": Account.AccountType.WALLET,
            "currency": Account.Currency.ARS,
            "initial_balance": Decimal("0.00"),
        },
    )
    if account.currency != payment.currency:
        raise ValidationError("La cuenta de Mercado Pago no coincide con la moneda del pago.")
    code, _ = MovementCode.objects.get_or_create(
        code="COBRO_EVENTO",
        defaults={
            "name": "Cobro de evento",
            "movement_type": MovementCode.MovementKind.INCOME,
            "category": "Eventos",
            "requires_event": True,
            "active": True,
        },
    )
    movement = CashMovement.objects.create(
        date_payment=_payment_accounting_date(payment_data),
        description=f"Cobro Mercado Pago - {payment.budget.event.name}",
        voucher_number=payment.mp_payment_id,
        movement_type=CashMovement.MovementType.INCOME,
        amount=payment.amount,
        account=account,
        code=code,
        event=payment.budget.event,
        payment_method="Mercado Pago",
        status=CashMovement.Status.CONFIRMED,
        notes=f"Preferencia {payment.mp_preference_id}",
    )
    payment.cash_movement = movement
    payment.save(update_fields=["cash_movement", "updated_at"])
    return movement


def ensure_event_budget_payment_reversal(payment, payment_data=None):
    if not payment.cash_movement_id:
        return None
    original = payment.cash_movement
    voucher_number = f"{payment.mp_payment_id or original.voucher_number}-reversal"
    existing = CashMovement.objects.filter(
        account=original.account,
        event=payment.budget.event,
        voucher_number=voucher_number,
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=payment.amount,
    ).first()
    if existing:
        return existing
    code = MovementCode.objects.filter(code="AJUSTE_CAJA").first() or original.code
    return CashMovement.objects.create(
        date_payment=_payment_accounting_date(payment_data or {}),
        description=f"Reversa Mercado Pago - {payment.budget.event.name}",
        voucher_number=voucher_number,
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=payment.amount,
        account=original.account,
        code=code,
        event=payment.budget.event,
        payment_method="Mercado Pago",
        status=CashMovement.Status.CONFIRMED,
        notes=f"Reversa de movimiento #{original.id}",
    )


def _validate_approved_budget_payment(payment, payment_data):
    if str(payment_data.get("status") or "").lower() != "approved":
        return
    errors = []
    expected_reference = f"event-budget-payment:{payment.id}"
    metadata = payment_data.get("metadata") or {}
    if str(payment_data.get("external_reference") or "") != expected_reference and str(metadata.get("event_budget_payment_id") or "") != str(payment.id):
        errors.append("external_reference")
    try:
        remote_amount = Decimal(str(payment_data.get("transaction_amount") or "-1"))
    except (InvalidOperation, TypeError):
        remote_amount = Decimal("-1")
    if remote_amount != payment.amount:
        errors.append("transaction_amount")
    if str(payment_data.get("currency_id") or "").upper() != payment.currency:
        errors.append("currency_id")
    expected_collector_id = str(settings.MERCADOPAGO_COLLECTOR_ID or "").strip()
    if expected_collector_id and str(payment_data.get("collector_id") or "").strip() != expected_collector_id:
        errors.append("collector_id")
    if errors:
        raise PaymentIntegrityError("El pago aprobado no coincide con el presupuesto: " + ", ".join(errors))


def parse_mp_signature_header(signature_header):
    ts_value = None
    v1_value = None
    for fragment in signature_header.split(","):
        key, _, value = fragment.partition("=")
        if key.strip().lower() == "ts":
            ts_value = value.strip()
        if key.strip().lower() == "v1":
            v1_value = value.strip()
    return ts_value, v1_value


def has_valid_mp_signature(request, payload):
    secret = str(settings.MERCADOPAGO_WEBHOOK_SECRET or "").strip()
    if not secret:
        return not settings.MERCADOPAGO_WEBHOOK_SIGNATURE_REQUIRED
    topic = str(request.query_params.get("type") or request.query_params.get("topic") or payload.get("type") or payload.get("topic") or "").strip()
    data_id = request.query_params.get("data.id") or str((payload.get("data") or {}).get("id") or "")
    if not data_id and topic == "payment":
        data_id = str(request.query_params.get("id") or payload.get("id") or "")
    ts_value, received_signature = parse_mp_signature_header(request.headers.get("x-signature", ""))
    request_id = request.headers.get("x-request-id", "")
    if not data_id or not request_id or not ts_value or not received_signature or not _has_fresh_mp_timestamp(ts_value):
        return False
    template = f"id:{str(data_id).lower()};request-id:{request_id};ts:{ts_value};"
    expected = hmac.new(secret.encode("utf-8"), template.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_signature)


def _has_fresh_mp_timestamp(ts_value):
    try:
        timestamp = int(ts_value)
    except (TypeError, ValueError):
        return False
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    tolerance = int(settings.MERCADOPAGO_WEBHOOK_SIGNATURE_TOLERANCE_SECONDS)
    return abs(int(timezone.now().timestamp()) - timestamp) <= tolerance


def build_mp_webhook_deduplication_key(topic, notification_id, payment_resource_id, payload):
    identity = f"{topic}:{notification_id}:{payment_resource_id}"
    if notification_id == "unknown" and not payment_resource_id:
        identity = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def get_or_create_event_budget(event):
    if not isinstance(event, Event):
        event = Event.objects.get(pk=event)
    budget, _created = EventBudget.objects.get_or_create(event=event)
    return budget


def get_event_budget_summary(event_or_budget):
    if isinstance(event_or_budget, EventBudget):
        budget = event_or_budget
    else:
        budget = EventBudget.objects.filter(event=event_or_budget).first()

    if not budget:
        return {
            "budget_id": None,
            "status": None,
            "item_count": 0,
            "subtotal": Decimal("0.00"),
            "optional_total": Decimal("0.00"),
            "grand_total": Decimal("0.00"),
        }

    return {
        "budget_id": budget.id,
        "status": budget.status,
        "item_count": budget.items.count(),
        "subtotal": budget.subtotal(),
        "optional_total": budget.optional_total(),
        "grand_total": budget.total(),
    }


def get_event_overview(event):
    if not isinstance(event, Event):
        event = Event.objects.select_related("client").get(pk=event)

    confirmed_movements = event.cash_movements.filter(status=CashMovement.Status.CONFIRMED)
    provider_entries = event.provider_ledger_entries.select_related("provider", "cash_movement")
    assignments = event.staff_assignments.select_related("employee", "role")
    employee_payments = event.employee_payments.select_related("employee", "assignment")

    total_income = _sum_amount(confirmed_movements.filter(movement_type=CashMovement.MovementType.INCOME))
    total_expense = _sum_amount(confirmed_movements.filter(movement_type=CashMovement.MovementType.EXPENSE))
    total_transfer_in = _sum_amount(confirmed_movements.filter(movement_type=CashMovement.MovementType.TRANSFER_IN))
    total_transfer_out = _sum_amount(confirmed_movements.filter(movement_type=CashMovement.MovementType.TRANSFER_OUT))
    provider_debt = _sum_amount(provider_entries.filter(entry_type=ProviderLedgerEntry.EntryType.DEBT))
    provider_payments = _sum_amount(provider_entries.filter(entry_type=ProviderLedgerEntry.EntryType.PAYMENT))
    staffing_cost = assignments.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    staffing_paid = employee_payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    staffing_pending = staffing_cost - staffing_paid
    budget_summary = get_event_budget_summary(event)

    return {
        "event": event,
        "linked_counts": {
            "movements": confirmed_movements.count(),
            "providers": provider_entries.count(),
            "assignments": assignments.count(),
            "employee_payments": employee_payments.count(),
        },
        "financial": {
            "income": total_income,
            "expense": total_expense,
            "transfer_in": total_transfer_in,
            "transfer_out": total_transfer_out,
            "result": total_income - total_expense,
            "provider_debt": provider_debt,
            "provider_payments": provider_payments,
            "staffing_cost": staffing_cost,
            "staffing_paid": staffing_paid,
            "staffing_pending": staffing_pending,
        },
        "service_snapshot": {
            "guest_count_dinner": event.guest_count_dinner or 0,
            "guest_count_toast": event.guest_count_toast or 0,
            "venue_space": event.venue_space,
            "main_table_notes": event.main_table_notes,
            "tableware_notes": event.tableware_notes,
            "internal_status": event.internal_status,
        },
        "budget_summary": budget_summary,
    }


@transaction.atomic
def close_daily_account(account, close_date, declared_balance, notes=""):
    if not isinstance(account, Account):
        account = Account.objects.select_for_update().get(pk=account)

    group, _ = DailyCashCloseGroup.objects.get_or_create(date=close_date)
    if group.status == DailyCashCloseGroup.Status.CLOSED and DailyAccountClose.objects.filter(
        close_group=group,
        account=account,
        closed_at__isnull=False,
    ).exists():
        raise ValidationError("La cuenta ya esta cerrada para esa fecha.")

    adjustment_code = MovementCode.objects.filter(code="AJUSTE_CAJA").first()
    day_movements = CashMovement.objects.filter(
        account=account,
        date_payment=close_date,
        status=CashMovement.Status.CONFIRMED,
    )
    adjustment_filter = Q(code=adjustment_code) if adjustment_code else Q(movement_type=CashMovement.MovementType.ADJUSTMENT)

    opening_balance = calculate_account_balance(account, before_date=close_date)
    total_income = _sum_amount(day_movements.filter(movement_type=CashMovement.MovementType.INCOME).exclude(adjustment_filter))
    total_expense = _sum_amount(day_movements.filter(movement_type=CashMovement.MovementType.EXPENSE).exclude(adjustment_filter))
    total_transfer_in = _sum_amount(day_movements.filter(movement_type=CashMovement.MovementType.TRANSFER_IN))
    total_transfer_out = _sum_amount(day_movements.filter(movement_type=CashMovement.MovementType.TRANSFER_OUT))
    positive_adjustments = _sum_amount(day_movements.filter(adjustment_filter).filter(movement_type=CashMovement.MovementType.ADJUSTMENT))
    negative_adjustments = _sum_amount(day_movements.filter(adjustment_filter).filter(movement_type=CashMovement.MovementType.EXPENSE))
    total_adjustments = positive_adjustments - negative_adjustments
    calculated_balance = (
        opening_balance
        + total_income
        - total_expense
        + total_transfer_in
        - total_transfer_out
        + total_adjustments
    )
    declared_balance = Decimal(str(declared_balance))
    daily_close, _ = DailyAccountClose.objects.update_or_create(
        close_group=group,
        account=account,
        defaults={
            "opening_balance": opening_balance,
            "total_income": total_income,
            "total_expense": total_expense,
            "total_transfer_in": total_transfer_in,
            "total_transfer_out": total_transfer_out,
            "total_adjustments": total_adjustments,
            "calculated_balance": calculated_balance,
            "declared_balance": declared_balance,
            "difference": declared_balance - calculated_balance,
            "notes": notes,
            "closed_at": timezone.now(),
        },
    )
    return daily_close


@transaction.atomic
def close_daily_cash_group(close_date, declared_balances=None, notes=""):
    declared_balances = declared_balances or {}
    group, _ = DailyCashCloseGroup.objects.get_or_create(date=close_date)
    if group.status == DailyCashCloseGroup.Status.CLOSED:
        raise ValidationError("El cierre diario general ya esta cerrado.")

    for account in Account.objects.filter(active=True):
        declared_balance = declared_balances.get(str(account.id), calculate_account_balance(account, up_to_date=close_date))
        close_daily_account(account, close_date, declared_balance)

    group.notes = notes
    group.status = DailyCashCloseGroup.Status.CLOSED
    group.closed_at = timezone.now()
    group.save(update_fields=["notes", "status", "closed_at", "updated_at"])
    return group


@transaction.atomic
def register_provider_payment(provider, account, amount, payment_date=None, event=None, description="", document_number="", user=None):
    if not isinstance(provider, Provider):
        provider = Provider.objects.get(pk=provider)
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    payment_date = payment_date or timezone.localdate()
    ensure_account_day_is_open(account, payment_date)
    amount = Decimal(str(amount))

    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=description or f"Pago a proveedor {provider.name}",
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=amount,
        account=account,
        code=get_code("PAGO_PROVEEDOR"),
        provider=provider,
        event=event,
        status=CashMovement.Status.CONFIRMED,
        created_by=user,
        updated_by=user,
    )
    ledger = ProviderLedgerEntry.objects.create(
        provider=provider,
        event=event,
        date=payment_date,
        entry_type=ProviderLedgerEntry.EntryType.PAYMENT,
        description=description or f"Pago a proveedor {provider.name}",
        document_number=document_number,
        amount=amount,
        cash_movement=movement,
    )
    return ledger


@transaction.atomic
def register_employee_payment(employee, account, amount, payment_date=None, assignment=None, event=None, notes="", user=None):
    if not isinstance(employee, Employee):
        employee = Employee.objects.get(pk=employee)
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    if assignment and not isinstance(assignment, EventStaffAssignment):
        assignment = EventStaffAssignment.objects.select_for_update().get(pk=assignment)
    payment_date = payment_date or timezone.localdate()
    ensure_account_day_is_open(account, payment_date)
    amount = Decimal(str(amount))
    event = event or (assignment.event if assignment else None)

    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=f"Pago personal eventual - {employee}",
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=amount,
        account=account,
        code=get_code("PERSONAL_EVENTUAL"),
        employee=employee,
        event=event,
        status=CashMovement.Status.CONFIRMED,
        notes=notes,
        created_by=user,
        updated_by=user,
    )
    payment = EmployeePayment.objects.create(
        employee=employee,
        event=event,
        assignment=assignment,
        cash_movement=movement,
        amount=amount,
        payment_date=payment_date,
        notes=notes,
    )

    if assignment:
        paid_amount = assignment.paid_amount()
        if paid_amount >= assignment.total_amount:
            assignment.status = EventStaffAssignment.Status.PAID
        elif paid_amount > 0:
            assignment.status = EventStaffAssignment.Status.PARTIALLY_PAID
        assignment.save(update_fields=["status", "updated_at"])
    return payment


@transaction.atomic
def register_tax_payment(
    tax_type,
    account,
    amount,
    payment_date=None,
    period="",
    notes="",
    reminder_due_date=None,
    recurrence_type=Reminder.RecurrenceType.NONE,
    remind_before_days=0,
    custom_days=None,
    user=None,
):
    if not isinstance(tax_type, TaxType):
        tax_type = TaxType.objects.get(pk=tax_type)
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    payment_date = payment_date or timezone.localdate()
    ensure_account_day_is_open(account, payment_date)
    amount = Decimal(str(amount))

    tax_payment = TaxPayment.objects.create(
        tax_type=tax_type,
        period=period,
        payment_date=payment_date,
        amount=amount,
        account=account,
        notes=notes,
    )
    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=f"Pago de impuesto - {tax_type.name}",
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=amount,
        account=account,
        code=get_code("IMPUESTOS"),
        tax_payment=tax_payment,
        status=CashMovement.Status.CONFIRMED,
        notes=notes,
        created_by=user,
        updated_by=user,
    )
    tax_payment.cash_movement = movement
    tax_payment.save(update_fields=["cash_movement", "updated_at"])

    reminder = None
    if reminder_due_date or recurrence_type != Reminder.RecurrenceType.NONE:
        reminder = create_next_tax_reminder(
            tax_payment=tax_payment,
            due_date=reminder_due_date,
            recurrence_type=recurrence_type,
            remind_before_days=remind_before_days,
            custom_days=custom_days,
        )
    return tax_payment, reminder


def add_months(value, months):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def create_next_tax_reminder(
    tax_payment,
    due_date=None,
    recurrence_type=Reminder.RecurrenceType.NONE,
    remind_before_days=0,
    custom_days=None,
):
    if due_date is None:
        base = tax_payment.payment_date
        if recurrence_type == Reminder.RecurrenceType.MONTHLY:
            due_date = add_months(base, 1)
        elif recurrence_type == Reminder.RecurrenceType.BIMONTHLY:
            due_date = add_months(base, 2)
        elif recurrence_type == Reminder.RecurrenceType.QUARTERLY:
            due_date = add_months(base, 3)
        elif recurrence_type == Reminder.RecurrenceType.YEARLY:
            due_date = add_months(base, 12)
        elif recurrence_type == Reminder.RecurrenceType.CUSTOM_DAYS and custom_days:
            due_date = base + timedelta(days=custom_days)
        else:
            due_date = base

    return Reminder.objects.create(
        title=f"Vencimiento {tax_payment.tax_type.name}",
        description=tax_payment.period,
        due_date=due_date,
        remind_before_days=remind_before_days,
        recurrence_type=recurrence_type,
        custom_days=custom_days,
        related_tax_payment=tax_payment,
    )


def get_dashboard_summary(summary_date=None):
    summary_date = summary_date or timezone.localdate()
    accounts = []
    balances_by_currency = {}
    for account in Account.objects.filter(active=True).order_by("currency", "name"):
        balance = calculate_account_balance(account, up_to_date=summary_date)
        accounts.append(
            {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "currency": account.currency,
                "balance": balance,
            }
        )
        balances_by_currency[account.currency] = balances_by_currency.get(account.currency, Decimal("0.00")) + balance

    today_movements = CashMovement.objects.filter(date_payment=summary_date, status=CashMovement.Status.CONFIRMED)
    reminders = Reminder.objects.filter(status=Reminder.Status.PENDING).filter(
        Q(due_date__lte=summary_date) | Q(due_date__lte=summary_date + timedelta(days=7))
    )
    today_closes = DailyAccountClose.objects.filter(close_group__date=summary_date).select_related("account", "close_group")
    closed_account_ids = set(today_closes.values_list("account_id", flat=True))
    pending_account_closes = [
        {
            "account_id": account.id,
            "account_name": account.name,
            "currency": account.currency,
            "balance": calculate_account_balance(account, up_to_date=summary_date),
        }
        for account in Account.objects.filter(active=True).order_by("currency", "name")
        if account.id not in closed_account_ids
    ]
    today_close_differences = [
        {
            "account_id": close.account_id,
            "account_name": close.account.name,
            "currency": close.account.currency,
            "declared_balance": close.declared_balance,
            "calculated_balance": close.calculated_balance,
            "difference": close.difference,
        }
        for close in today_closes
        if close.difference != 0
    ]
    providers_with_credit = []
    for provider in Provider.objects.filter(active=True).order_by("name"):
        balance = provider.balance()
        if balance < 0:
            providers_with_credit.append(
                {
                    "provider_id": provider.id,
                    "provider_name": provider.name,
                    "balance": balance,
                }
            )
    providers_with_credit.sort(key=lambda item: item["balance"])

    employee_pending = []
    for assignment in (
        EventStaffAssignment.objects.exclude(status=EventStaffAssignment.Status.CANCELLED)
        .select_related("employee", "event", "role")
        .order_by("work_date")
    ):
        pending = assignment.pending_amount()
        if pending > 0:
            employee_pending.append(
                {
                    "assignment_id": assignment.id,
                    "employee_name": str(assignment.employee),
                    "event_name": assignment.event.name,
                    "role_name": assignment.role.name,
                    "work_date": assignment.work_date,
                    "total_amount": assignment.total_amount,
                    "pending_amount": pending,
                    "status": assignment.status,
                }
            )

    return {
        "date": summary_date,
        "accounts": accounts,
        "balances_by_currency": [
            {"currency": currency, "balance": balance}
            for currency, balance in sorted(balances_by_currency.items())
        ],
        "today_income": _sum_amount(today_movements.filter(movement_type=CashMovement.MovementType.INCOME)),
        "today_expense": _sum_amount(today_movements.filter(movement_type=CashMovement.MovementType.EXPENSE)),
        "pending_reminders": reminders.order_by("due_date")[:10],
        "pending_account_closes": pending_account_closes,
        "today_close_differences": today_close_differences,
        "providers_with_credit": providers_with_credit[:10],
        "employee_pending": employee_pending[:10],
        "voided_count": CashMovement.objects.filter(status=CashMovement.Status.VOIDED).count(),
    }
