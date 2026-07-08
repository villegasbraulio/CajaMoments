from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import logging
import csv
from io import StringIO
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date as parse_iso_date, parse_datetime

from .models import (
    Account,
    AccountTransfer,
    AuditLogEntry,
    CashMovement,
    Client,
    DailyAccountClose,
    DailyCashCloseGroup,
    Employee,
    EmployeePayment,
    Event,
    EventBudget,
    EventBudgetItem,
    EventBudgetPayment,
    EventStaffAssignment,
    Graduate,
    GraduationEvent,
    GraduationTicketPrice,
    MovementCode,
    Provider,
    ProviderLedgerEntry,
    Reminder,
    ServiceType,
    TaxPayment,
    TicketPurchase,
    TaxType,
)

try:
    import mercadopago
    from mercadopago.config import RequestOptions
except ImportError:
    mercadopago = None
    RequestOptions = None


logger = logging.getLogger(__name__)


def _clean_email(value):
    value = str(value or "").strip()
    if not value or value.endswith("@cajamoments.local"):
        return ""
    validate_email(value)
    return value


def _movement_receipt_recipients(movement, recipient_email=""):
    candidates = [
        recipient_email,
        getattr(getattr(movement, "provider", None), "email", ""),
        getattr(getattr(movement, "employee", None), "email", ""),
        getattr(getattr(getattr(movement, "event", None), "client", None), "email", ""),
        getattr(getattr(movement, "event", None), "contact_email", ""),
    ]
    recipients = []
    for candidate in candidates:
        email = _clean_email(candidate)
        if email and email not in recipients:
            recipients.append(email)
    return recipients


def audit_log(user, action, obj=None, detail=""):
    if obj is None:
        model_name = ""
        object_id = ""
    else:
        model_name = obj.__class__.__name__
        object_id = str(getattr(obj, "pk", "") or "")
    return AuditLogEntry.objects.create(user=user, action=action, model_name=model_name, object_id=object_id, detail=detail)


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
        title = f"Presupuesto {event.name}"
        description = event.get_event_type_display() or "Evento"
        if payment.budget_item_id:
            title = payment.budget_item.service_name
            description = f"Item presupuesto - {event.name}"
        payload = {
            "items": [
                {
                    "id": f"event-budget-payment:{payment.id}",
                    "title": title,
                    "description": description,
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
            custom_headers={"x-idempotency-key": str(payment.idempotency_key)},
        )
        response = self.sdk.preference().create(payload, request_options)
        return self._unwrap_response(response, "No pudimos crear la preferencia de pago.")

    def create_ticket_preference(self, purchase):
        event = purchase.graduation_event.event
        payload = {
            "items": [
                {
                    "id": f"ticket-purchase:{purchase.id}",
                    "title": f"Tarjetas {event.name}",
                    "description": str(purchase.graduate),
                    "currency_id": Account.Currency.ARS,
                    "quantity": 1,
                    "unit_price": float(purchase.total_amount),
                }
            ],
            "external_reference": f"ticket-purchase:{purchase.id}",
            "metadata": {
                "ticket_purchase_id": str(purchase.id),
                "graduation_event_id": str(purchase.graduation_event_id),
                "event_id": str(event.id),
            },
            "payer": {"email": purchase.email},
            "payment_methods": {"installments": 6},
        }
        notification_url = self._build_ticket_notification_url()
        if notification_url:
            payload["notification_url"] = notification_url
        back_urls = self._build_ticket_back_urls(purchase)
        if back_urls:
            payload["back_urls"] = back_urls
            payload["auto_return"] = "approved"
        request_options = RequestOptions(
            access_token=self.access_token,
            custom_headers={"x-idempotency-key": str(purchase.idempotency_key)},
        )
        response = self.sdk.preference().create(payload, request_options)
        return self._unwrap_response(response, "No pudimos crear la preferencia de tarjetas.")

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
        query = urlencode({"payment": payment.id})
        token = payment.budget.event.public_payment_token
        return {
            "success": f"{frontend_url}/pagar-evento/{token}/?payment_status=approved&{query}",
            "failure": f"{frontend_url}/pagar-evento/{token}/?payment_status=failure&{query}",
            "pending": f"{frontend_url}/pagar-evento/{token}/?payment_status=pending&{query}",
        }

    def _build_notification_url(self):
        backend_url = _resolve_public_base_url(settings.BACKEND_URL)
        return f"{backend_url}/api/event-budget-payments/webhook/" if backend_url else None

    def _build_ticket_notification_url(self):
        backend_url = _resolve_public_base_url(settings.BACKEND_URL)
        return f"{backend_url}/api/ticket-purchases/webhook/" if backend_url else None

    def _build_ticket_back_urls(self, purchase):
        frontend_url = _resolve_public_base_url(settings.FRONTEND_URL)
        if not frontend_url:
            return {}
        query = urlencode({"purchase": purchase.id})
        token = purchase.graduation_event.public_token
        return {
            "success": f"{frontend_url}/egresados/{token}/?payment_status=approved&{query}",
            "failure": f"{frontend_url}/egresados/{token}/?payment_status=failure&{query}",
            "pending": f"{frontend_url}/egresados/{token}/?payment_status=pending&{query}",
        }

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


EVENT_BASE_ITEM_NAME = "Evento"
ACTIVE_BUDGET_PAYMENT_STATUSES = [
    EventBudgetPayment.Status.PENDING,
    EventBudgetPayment.Status.IN_PROCESS,
    EventBudgetPayment.Status.APPROVED,
]


def _payment_purpose_for(budget_item=None, payment_purpose=None, is_deposit=False):
    if budget_item:
        return EventBudgetPayment.Purpose.BUDGET_ITEM
    if payment_purpose == EventBudgetPayment.Purpose.BUDGET_ITEM:
        raise ValidationError("Elegi un servicio para pagar.")
    if payment_purpose in EventBudgetPayment.Purpose.values:
        return payment_purpose
    return EventBudgetPayment.Purpose.DEPOSIT if is_deposit else EventBudgetPayment.Purpose.ADVANCE


def budget_purpose_is_registered(budget, payment_purpose):
    return budget.payments.filter(
        status__in=ACTIVE_BUDGET_PAYMENT_STATUSES,
        payment_purpose=payment_purpose,
        budget_item__isnull=True,
    ).exists()


def _approved_budget_item_paid_amount(budget_item):
    return budget_item.payments.filter(status=EventBudgetPayment.Status.APPROVED).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def _budget_payment_label(payment):
    if payment.payment_purpose == EventBudgetPayment.Purpose.DEPOSIT:
        return "Seña de evento"
    if payment.payment_purpose == EventBudgetPayment.Purpose.BUDGET_ITEM and payment.budget_item_id:
        return f"Cobro servicio - {payment.budget_item.service_name}"
    return "Adelanto de evento"


def _budget_payment_code_defaults(payment_purpose):
    if payment_purpose == EventBudgetPayment.Purpose.DEPOSIT:
        return "SEÑA_EVENTO", "Seña de evento"
    if payment_purpose == EventBudgetPayment.Purpose.BUDGET_ITEM:
        return "COBRO_EVENTO", "Cobro de servicio"
    return "ADELANTO_EVENTO", "Adelanto de evento"


def _budget_payment_amount(budget, budget_item=None, amount=None):
    if amount is not None and amount != "":
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError("El importe debe ser mayor a cero.")
        return amount
    if budget_item:
        if budget_item.budget_id != budget.id:
            raise ValidationError("El item no pertenece al presupuesto.")
        pending = budget_item.total - _approved_budget_item_paid_amount(budget_item)
        if pending <= 0:
            raise ValidationError("Este servicio ya esta pagado.")
        return pending
    return budget.total()


@transaction.atomic
def create_event_budget_payment_preference(budget, budget_item=None, amount=None, receipt_email="", payment_purpose=None):
    if not isinstance(budget, EventBudget):
        budget = EventBudget.objects.select_for_update().select_related("event", "event__client").get(pk=budget)
    else:
        budget = EventBudget.objects.select_for_update().select_related("event", "event__client").get(pk=budget.pk)
    if budget_item and not isinstance(budget_item, EventBudgetItem):
        budget_item = EventBudgetItem.objects.select_related("budget").get(pk=budget_item)
    purpose = _payment_purpose_for(budget_item=budget_item, payment_purpose=payment_purpose)
    if purpose == EventBudgetPayment.Purpose.DEPOSIT and budget_purpose_is_registered(budget, purpose):
        raise ValidationError("La seña ya esta registrada.")
    amount = _budget_payment_amount(budget, budget_item, amount)
    if amount <= 0:
        raise ValidationError("El presupuesto no tiene importe para cobrar.")
    reusable = (
        budget.payments.select_for_update()
        .filter(
            amount=amount,
            budget_item=budget_item,
            payment_purpose=purpose,
            currency=Account.Currency.ARS,
            receipt_email=_clean_email(receipt_email),
            status__in=[EventBudgetPayment.Status.PENDING, EventBudgetPayment.Status.IN_PROCESS],
        )
        .exclude(mp_preference_id="")
        .first()
    )
    payment = reusable or EventBudgetPayment.objects.create(
        budget=budget,
        budget_item=budget_item,
        payment_purpose=purpose,
        amount=amount,
        currency=Account.Currency.ARS,
        receipt_email=_clean_email(receipt_email),
    )
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


@transaction.atomic
def set_event_base_amount(event, amount):
    if not isinstance(event, Event):
        event = Event.objects.select_for_update().get(pk=event)
    amount = Decimal(str(amount or "0.00"))
    if amount < 0:
        raise ValidationError("El monto del evento no puede ser negativo.")
    budget = get_or_create_event_budget(event)
    item, _created = EventBudgetItem.objects.update_or_create(
        budget=budget,
        service_name=EVENT_BASE_ITEM_NAME,
        is_optional=False,
        defaults={
            "category": "Base",
            "quantity": Decimal("1.00"),
            "unit_label": "evento",
            "unit_price": amount,
            "sort_order": 0,
            "notes": "Monto base del evento.",
        },
    )
    return item


@transaction.atomic
def create_event_with_client_and_amount(event_data, client_data, amount=None, user=None):
    client_name = str(client_data.get("name") or event_data.get("contact_name") or "").strip()
    if not client_name:
        raise ValidationError("El nombre del cliente es obligatorio.")
    client = Client.objects.create(
        name=client_name,
        phone=str(client_data.get("phone") or "").strip(),
        email=str(client_data.get("email") or "").strip(),
        notes=str(client_data.get("notes") or "").strip(),
    )
    event = Event.objects.create(client=client, **event_data)
    if amount not in (None, ""):
        set_event_base_amount(event, amount)
    audit_log(user, "event_client_create", event, f"Cliente #{client.id} creado con el evento.")
    return event


@transaction.atomic
def register_event_payment(event, account, amount, payment_date=None, payment_method="Manual", description="", is_deposit=False, budget_item=None, receipt_email="", user=None, payment_purpose=None):
    if not isinstance(event, Event):
        event = Event.objects.select_for_update().get(pk=event)
    if event.closed_at:
        raise ValidationError("El evento esta cerrado.")
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    if budget_item and not isinstance(budget_item, EventBudgetItem):
        budget_item = EventBudgetItem.objects.select_related("budget").get(pk=budget_item)
    budget = get_or_create_event_budget(event)
    if budget_item and budget_item.budget_id != budget.id:
        raise ValidationError("El item no pertenece al evento.")
    purpose = _payment_purpose_for(budget_item=budget_item, payment_purpose=payment_purpose, is_deposit=is_deposit)
    if purpose == EventBudgetPayment.Purpose.DEPOSIT and budget_purpose_is_registered(budget, purpose):
        raise ValidationError("La seña ya esta registrada.")
    payment_date = payment_date or timezone.localdate()
    ensure_account_day_is_open(account, payment_date)
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("El importe debe ser mayor a cero.")
    if budget_item:
        pending = budget_item.total - _approved_budget_item_paid_amount(budget_item)
        if pending <= 0:
            raise ValidationError("Este servicio ya esta pagado.")
        if amount > pending:
            raise ValidationError("El importe supera el saldo pendiente del servicio.")
    payment = EventBudgetPayment.objects.create(
        budget=budget,
        budget_item=budget_item,
        payment_purpose=purpose,
        status=EventBudgetPayment.Status.APPROVED,
        amount=amount,
        currency=account.currency,
        payment_method=payment_method,
        receipt_email=_clean_email(receipt_email),
    )
    code_value, code_name = _budget_payment_code_defaults(purpose)
    code, _ = MovementCode.objects.get_or_create(
        code=code_value,
        defaults={
            "name": code_name,
            "movement_type": MovementCode.MovementKind.INCOME,
            "category": "Eventos",
            "requires_event": True,
            "active": True,
        },
    )
    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=description or _budget_payment_label(payment),
        movement_type=CashMovement.MovementType.INCOME,
        amount=amount,
        account=account,
        code=code,
        event=event,
        payment_method=payment_method,
        status=CashMovement.Status.CONFIRMED,
        notes=f"Pago presupuesto #{budget.id}" + (f" - Item #{budget_item.id}" if budget_item else ""),
        created_by=user,
        updated_by=user,
    )
    payment.cash_movement = movement
    payment.save(update_fields=["cash_movement", "updated_at"])
    send_cash_movement_receipt_email(movement, payment.receipt_email)
    if purpose == EventBudgetPayment.Purpose.DEPOSIT and event.status == Event.Status.DRAFT:
        event.status = Event.Status.SIGNALED
        event.save(update_fields=["status", "updated_at"])
    audit_log(user, "event_payment", movement, f"Evento #{event.id}")
    return payment


@transaction.atomic
def register_event_budget_item_manual_payment(budget_item, account, amount=None, payment_date=None, payment_method="Manual", description="", receipt_email="", user=None):
    if not isinstance(budget_item, EventBudgetItem):
        budget_item = EventBudgetItem.objects.select_related("budget", "budget__event").get(pk=budget_item)
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    payment_date = payment_date or timezone.localdate()
    ensure_account_day_is_open(account, payment_date)
    pending = budget_item.total - _approved_budget_item_paid_amount(budget_item)
    if pending <= 0:
        raise ValidationError("Este servicio ya esta pagado.")
    amount = Decimal(str(amount or pending))
    if amount <= 0:
        raise ValidationError("El importe debe ser mayor a cero.")
    if amount > pending:
        raise ValidationError("El importe supera el saldo pendiente del servicio.")
    payment = EventBudgetPayment.objects.create(
        budget=budget_item.budget,
        budget_item=budget_item,
        payment_purpose=EventBudgetPayment.Purpose.BUDGET_ITEM,
        status=EventBudgetPayment.Status.APPROVED,
        amount=amount,
        currency=account.currency,
        payment_method=payment_method,
        receipt_email=_clean_email(receipt_email),
    )
    code = get_code("COBRO_EVENTO")
    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=description or f"Cobro item - {budget_item.service_name}",
        movement_type=CashMovement.MovementType.INCOME,
        amount=amount,
        account=account,
        code=code,
        event=budget_item.budget.event,
        payment_method=payment_method,
        status=CashMovement.Status.CONFIRMED,
        notes=f"Item presupuesto #{budget_item.id}",
        created_by=user,
        updated_by=user,
    )
    payment.cash_movement = movement
    payment.save(update_fields=["cash_movement", "updated_at"])
    send_cash_movement_receipt_email(movement, payment.receipt_email)
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
    code_value, code_name = _budget_payment_code_defaults(payment.payment_purpose)
    code, _ = MovementCode.objects.get_or_create(
        code=code_value,
        defaults={
            "name": code_name,
            "movement_type": MovementCode.MovementKind.INCOME,
            "category": "Eventos",
            "requires_event": True,
            "active": True,
        },
    )
    movement = CashMovement.objects.create(
        date_payment=_payment_accounting_date(payment_data),
        description=f"Mercado Pago - {_budget_payment_label(payment)}",
        voucher_number=payment.mp_payment_id,
        movement_type=CashMovement.MovementType.INCOME,
        amount=payment.amount,
        account=account,
        code=code,
        event=payment.budget.event,
        payment_method="Mercado Pago",
        status=CashMovement.Status.CONFIRMED,
        notes=f"Preferencia {payment.mp_preference_id}" + (f" - Item presupuesto #{payment.budget_item_id}" if payment.budget_item_id else ""),
    )
    payment.cash_movement = movement
    payment.save(update_fields=["cash_movement", "updated_at"])
    payer_email = ((payment_data.get("payer") or {}).get("email") if isinstance(payment_data, dict) else "") or ""
    send_cash_movement_receipt_email(movement, payment.receipt_email or payer_email)
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


def _validate_capacity(graduation_event, quantity):
    if graduation_event.capacity is None:
        return
    if graduation_event.paid_ticket_count() + int(quantity) > graduation_event.capacity:
        raise ValidationError("No hay cupo suficiente para esa cantidad de tarjetas.")


def _validate_graduate_ticket_limit(graduation_event, graduate, quantity):
    if graduation_event.max_tickets_per_graduate is None:
        return
    current = (
        graduate.ticket_purchases.filter(status__in=[TicketPurchase.Status.PAID, TicketPurchase.Status.IN_PROCESS, TicketPurchase.Status.PENDING])
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    if current + int(quantity) > graduation_event.max_tickets_per_graduate:
        raise ValidationError("La cantidad supera el maximo acumulado permitido para este egresado.")


@transaction.atomic
def create_ticket_purchase_preference(graduation_event, graduate, quantity, email):
    if not isinstance(graduation_event, GraduationEvent):
        graduation_event = GraduationEvent.objects.select_for_update().select_related("event").get(pk=graduation_event)
    if not isinstance(graduate, Graduate):
        graduate = Graduate.objects.get(pk=graduate)
    if graduate.graduation_event_id != graduation_event.id:
        raise ValidationError("El egresado no pertenece a este evento.")
    if not graduation_event.active:
        raise ValidationError("La venta de tarjetas no esta activa.")
    if graduation_event.closed_at:
        raise ValidationError("La lista de egresados ya esta cerrada.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValidationError("La cantidad debe ser mayor a cero.")
    if quantity < 1:
        raise ValidationError("La cantidad debe ser mayor a cero.")
    if not str(email or "").strip():
        raise ValidationError("El email es obligatorio.")
    _validate_capacity(graduation_event, quantity)
    _validate_graduate_ticket_limit(graduation_event, graduate, quantity)
    purchase = TicketPurchase.objects.create(
        graduation_event=graduation_event,
        graduate=graduate,
        quantity=quantity,
        email=email,
        payment_date=timezone.localdate(),
    )
    _send_ticket_purchase_summary(purchase)
    preference = MercadoPagoClient().create_ticket_preference(purchase)
    preference_id = str(preference.get("id") or "")
    if not preference_id:
        raise MercadoPagoAPIError("Mercado Pago no devolvio una preferencia valida.")
    purchase.mp_preference_id = preference_id
    purchase.preference_init_point = str(preference.get("init_point") or "")
    purchase.preference_sandbox_init_point = str(preference.get("sandbox_init_point") or "")
    purchase.save(update_fields=["mp_preference_id", "preference_init_point", "preference_sandbox_init_point", "updated_at"])
    return purchase


def create_graduation_ticket_price(graduation_event, price, valid_from=None, valid_until=None, notes=""):
    if not isinstance(graduation_event, GraduationEvent):
        graduation_event = GraduationEvent.objects.get(pk=graduation_event)
    valid_from = valid_from or timezone.localdate().replace(day=1)
    if valid_until and valid_until < valid_from:
        raise ValidationError("La vigencia hasta no puede ser anterior a la vigencia desde.")
    return GraduationTicketPrice.objects.update_or_create(
        graduation_event=graduation_event,
        valid_from=valid_from,
        defaults={"price": Decimal(str(price)), "valid_until": valid_until, "notes": notes},
    )[0]


@transaction.atomic
def register_ticket_purchase_manual(graduation_event, graduate, quantity, account, email="", payment_date=None, payment_method="Efectivo", user=None):
    if not isinstance(graduation_event, GraduationEvent):
        graduation_event = GraduationEvent.objects.select_for_update().select_related("event").get(pk=graduation_event)
    if not isinstance(graduate, Graduate):
        graduate = Graduate.objects.get(pk=graduate)
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    if graduation_event.closed_at:
        raise ValidationError("La lista de egresados ya esta cerrada.")
    if graduate.graduation_event_id != graduation_event.id:
        raise ValidationError("El egresado no pertenece a este evento.")
    payment_date = payment_date or timezone.localdate()
    quantity = int(quantity)
    _validate_capacity(graduation_event, quantity)
    _validate_graduate_ticket_limit(graduation_event, graduate, quantity)
    ensure_account_day_is_open(account, payment_date)
    purchase = TicketPurchase.objects.create(
        graduation_event=graduation_event,
        graduate=graduate,
        quantity=quantity,
        email=email or "sin-email@cajamoments.local",
        status=TicketPurchase.Status.PAID,
        payment_method=payment_method,
        payment_date=payment_date,
        created_by=user,
    )
    code = get_code("COBRO_EVENTO")
    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=f"Venta manual tarjetas egresados - {graduate}",
        movement_type=CashMovement.MovementType.INCOME,
        amount=purchase.total_amount,
        account=account,
        code=code,
        event=graduation_event.event,
        payment_method=payment_method,
        status=CashMovement.Status.CONFIRMED,
        notes=f"Compra manual tarjetas #{purchase.id}",
        created_by=user,
        updated_by=user,
    )
    purchase.cash_movement = movement
    purchase.save(update_fields=["cash_movement", "updated_at"])
    send_cash_movement_receipt_email(movement, purchase.email)
    audit_log(user, "ticket_purchase_manual", purchase, f"{quantity} tarjetas")
    return purchase


@transaction.atomic
def close_graduation_event(graduation_event, user=None):
    if not isinstance(graduation_event, GraduationEvent):
        graduation_event = GraduationEvent.objects.select_for_update().get(pk=graduation_event)
    if graduation_event.closed_at:
        return graduation_event
    graduation_event.closed_at = timezone.now()
    graduation_event.closed_by = user
    graduation_event.active = False
    graduation_event.save(update_fields=["closed_at", "closed_by", "active", "updated_at"])
    audit_log(user, "graduation_close", graduation_event)
    return graduation_event


def export_graduation_event_csv(graduation_event):
    if not isinstance(graduation_event, GraduationEvent):
        graduation_event = GraduationEvent.objects.get(pk=graduation_event)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Egresado", "Cantidad", "Importe", "Email", "Estado", "Medio", "Fecha", "Movimiento caja"])
    for purchase in graduation_event.purchases.select_related("graduate", "cash_movement").order_by("graduate__last_name", "graduate__first_name", "created_at"):
        writer.writerow([
            str(purchase.graduate),
            purchase.quantity,
            purchase.total_amount,
            purchase.email,
            purchase.status,
            purchase.payment_method,
            purchase.payment_date or "",
            purchase.cash_movement_id or "",
        ])
    return output.getvalue()


def _send_ticket_purchase_summary(purchase):
    event = purchase.graduation_event.event
    send_mail(
        subject=f"Resumen de compra - {event.name}",
        message=(
            f"Egresado: {purchase.graduate}\n"
            f"Cantidad de tarjetas: {purchase.quantity}\n"
            f"Importe total: ${purchase.total_amount}\n"
            "El pago se completa en Mercado Pago."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[purchase.email],
    )


TICKET_STATUS_MAP = {
    "approved": TicketPurchase.Status.PAID,
    "in_process": TicketPurchase.Status.IN_PROCESS,
    "pending": TicketPurchase.Status.PENDING,
    "authorized": TicketPurchase.Status.PENDING,
    "rejected": TicketPurchase.Status.CANCELLED,
    "cancelled": TicketPurchase.Status.CANCELLED,
    "refunded": TicketPurchase.Status.REFUNDED,
    "charged_back": TicketPurchase.Status.REFUNDED,
}


@transaction.atomic
def sync_ticket_purchase_payment(purchase_id, payment_data):
    purchase = TicketPurchase.objects.select_for_update().select_related("graduation_event", "graduation_event__event", "graduate", "cash_movement").get(pk=purchase_id)
    _validate_approved_ticket_purchase(purchase, payment_data)
    raw_status = str(payment_data.get("status") or "pending").lower()
    purchase.status = TICKET_STATUS_MAP.get(raw_status, TicketPurchase.Status.PENDING)
    purchase.mp_payment_id = str(payment_data.get("id") or purchase.mp_payment_id)
    purchase.status_detail = str(payment_data.get("status_detail") or "")
    purchase.payment_method = str(payment_data.get("payment_method_id") or "")
    purchase.payment_type = str(payment_data.get("payment_type_id") or "")
    purchase.save(update_fields=["status", "mp_payment_id", "status_detail", "payment_method", "payment_type", "updated_at"])
    if purchase.status == TicketPurchase.Status.PAID:
        ensure_ticket_purchase_cash_movement(purchase, payment_data)
    elif raw_status in {"refunded", "charged_back"}:
        ensure_ticket_purchase_reversal(purchase, payment_data)
    return purchase


def _validate_approved_ticket_purchase(purchase, payment_data):
    if str(payment_data.get("status") or "").lower() != "approved":
        return
    errors = []
    expected_reference = f"ticket-purchase:{purchase.id}"
    metadata = payment_data.get("metadata") or {}
    if str(payment_data.get("external_reference") or "") != expected_reference and str(metadata.get("ticket_purchase_id") or "") != str(purchase.id):
        errors.append("external_reference")
    try:
        remote_amount = Decimal(str(payment_data.get("transaction_amount") or "-1"))
    except (InvalidOperation, TypeError):
        remote_amount = Decimal("-1")
    if remote_amount != purchase.total_amount:
        errors.append("transaction_amount")
    if str(payment_data.get("currency_id") or "").upper() != Account.Currency.ARS:
        errors.append("currency_id")
    if errors:
        raise PaymentIntegrityError("El pago aprobado no coincide con la compra: " + ", ".join(errors))


def ensure_ticket_purchase_cash_movement(purchase, payment_data=None):
    if purchase.cash_movement_id:
        return purchase.cash_movement
    payment_data = payment_data or {}
    account_name = str(settings.MERCADOPAGO_ACCOUNT_NAME or "MERCADO PAGO").strip() or "MERCADO PAGO"
    account, _ = Account.objects.get_or_create(
        name=account_name,
        defaults={"type": Account.AccountType.WALLET, "currency": Account.Currency.ARS, "initial_balance": Decimal("0.00")},
    )
    code, _ = MovementCode.objects.get_or_create(
        code="COBRO_EVENTO",
        defaults={"name": "Cobro de evento", "movement_type": MovementCode.MovementKind.INCOME, "category": "Eventos", "requires_event": True, "active": True},
    )
    movement = CashMovement.objects.create(
        date_payment=_payment_accounting_date(payment_data),
        description=f"Venta tarjetas egresados - {purchase.graduate}",
        voucher_number=purchase.mp_payment_id,
        movement_type=CashMovement.MovementType.INCOME,
        amount=purchase.total_amount,
        account=account,
        code=code,
        event=purchase.graduation_event.event,
        payment_method="Mercado Pago",
        status=CashMovement.Status.CONFIRMED,
        notes=f"Compra tarjetas #{purchase.id}",
    )
    purchase.cash_movement = movement
    purchase.payment_date = movement.date_payment
    purchase.save(update_fields=["cash_movement", "payment_date", "updated_at"])
    send_cash_movement_receipt_email(movement, purchase.email)
    return movement


def ensure_ticket_purchase_reversal(purchase, payment_data=None):
    if not purchase.cash_movement_id:
        return None
    original = purchase.cash_movement
    voucher_number = f"{purchase.mp_payment_id or original.voucher_number}-ticket-reversal"
    existing = CashMovement.objects.filter(
        account=original.account,
        event=purchase.graduation_event.event,
        voucher_number=voucher_number,
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=purchase.total_amount,
    ).first()
    if existing:
        return existing
    code = MovementCode.objects.filter(code="AJUSTE_CAJA").first() or original.code
    return CashMovement.objects.create(
        date_payment=_payment_accounting_date(payment_data or {}),
        description=f"Reversa tarjetas egresados - {purchase.graduate}",
        voucher_number=voucher_number,
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=purchase.total_amount,
        account=original.account,
        code=code,
        event=purchase.graduation_event.event,
        payment_method="Mercado Pago",
        status=CashMovement.Status.CONFIRMED,
        notes=f"Reversa de compra tarjetas #{purchase.id}",
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


def _event_paid_amount(event):
    return _sum_amount(event.cash_movements.filter(status=CashMovement.Status.CONFIRMED, movement_type=CashMovement.MovementType.INCOME))


def _event_expense_amount(event):
    return _sum_amount(event.cash_movements.filter(status=CashMovement.Status.CONFIRMED, movement_type=CashMovement.MovementType.EXPENSE))


def get_event_overview(event):
    if not isinstance(event, Event):
        event = Event.objects.select_related("client").get(pk=event)

    confirmed_movements = event.cash_movements.filter(status=CashMovement.Status.CONFIRMED)
    provider_entries = event.provider_ledger_entries.select_related("provider", "cash_movement")
    assignments = event.staff_assignments.select_related("employee", "role")
    employee_payments = event.employee_payments.select_related("employee", "assignment")

    total_income = _event_paid_amount(event)
    total_expense = _event_expense_amount(event)
    total_transfer_in = _sum_amount(confirmed_movements.filter(movement_type=CashMovement.MovementType.TRANSFER_IN))
    total_transfer_out = _sum_amount(confirmed_movements.filter(movement_type=CashMovement.MovementType.TRANSFER_OUT))
    provider_debt = _sum_amount(provider_entries.filter(entry_type=ProviderLedgerEntry.EntryType.DEBT))
    provider_payments = _sum_amount(provider_entries.filter(entry_type=ProviderLedgerEntry.EntryType.PAYMENT))
    staffing_cost = assignments.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    staffing_paid = employee_payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    staffing_pending = staffing_cost - staffing_paid
    budget_summary = get_event_budget_summary(event)
    event_total = budget_summary["grand_total"]
    pending_amount = max(event_total - total_income, Decimal("0.00"))

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
            "event_total": event_total,
            "paid": total_income,
            "pending": pending_amount,
            "expenses": total_expense,
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
def close_event(event, user=None):
    if not isinstance(event, Event):
        event = Event.objects.select_for_update().get(pk=event)
    else:
        event = Event.objects.select_for_update().get(pk=event.pk)
    if event.closed_at:
        return event
    overview = get_event_overview(event)
    event.status = Event.Status.CLOSED
    event.closed_at = timezone.now()
    event.closed_by = user
    event.closed_total_amount = overview["financial"]["event_total"]
    event.closed_paid_amount = overview["financial"]["paid"]
    event.closed_pending_amount = overview["financial"]["pending"]
    event.closed_expense_amount = overview["financial"]["expenses"]
    event.closed_result_amount = overview["financial"]["result"]
    event.save(
        update_fields=[
            "status",
            "closed_at",
            "closed_by",
            "closed_total_amount",
            "closed_paid_amount",
            "closed_pending_amount",
            "closed_expense_amount",
            "closed_result_amount",
            "updated_at",
        ]
    )
    audit_log(user, "event_close", event, "Numeros finales congelados.")
    return event


def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_cash_movement_receipt_pdf(movement):
    if not isinstance(movement, CashMovement):
        movement = CashMovement.objects.select_related("account", "code", "provider", "employee", "event").get(pk=movement)
    if movement.status != CashMovement.Status.CONFIRMED:
        raise ValidationError("Solo se generan comprobantes para movimientos confirmados.")
    title = "Recibo" if movement.movement_type in (CashMovement.MovementType.INCOME, CashMovement.MovementType.TRANSFER_IN, CashMovement.MovementType.ADJUSTMENT) else "Comprobante de pago"
    related = movement.event or movement.provider or movement.employee or ""
    lines = [
        title,
        f"Nro: CM-{movement.id:06d}",
        f"Fecha: {movement.date_payment}",
        f"Cuenta: {movement.account.name}",
        f"Codigo: {movement.code.code} - {movement.code.name}",
        f"Concepto: {movement.description}",
        f"Importe: {movement.account.currency} {movement.amount}",
        f"Medio de pago: {movement.payment_method or '-'}",
        f"Relacionado: {related or '-'}",
        f"Comprobante externo: {movement.voucher_number or '-'}",
    ]
    if movement.notes:
        lines.append(f"Notas: {movement.notes}")
    text = "BT /F1 12 Tf 72 760 Td 18 TL " + " ".join(f"({_pdf_escape(line)}) Tj T*" for line in lines) + " ET"
    stream = text.encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)


def send_cash_movement_receipt_email(movement, recipient_email=""):
    if not isinstance(movement, CashMovement):
        movement = CashMovement.objects.select_related("account", "code", "provider", "employee", "event", "event__client").get(pk=movement)
    recipients = _movement_receipt_recipients(movement, recipient_email)
    if movement.status != CashMovement.Status.CONFIRMED or not recipients:
        return False

    def _send():
        try:
            refreshed = CashMovement.objects.select_related("account", "code", "provider", "employee", "event", "event__client").get(pk=movement.pk)
            pdf = build_cash_movement_receipt_pdf(refreshed)
            title = "Recibo" if refreshed.movement_type in (CashMovement.MovementType.INCOME, CashMovement.MovementType.TRANSFER_IN, CashMovement.MovementType.ADJUSTMENT) else "Comprobante de pago"
            message = EmailMessage(
                subject=f"{title} CM-{refreshed.id:06d}",
                body=f"Adjuntamos el comprobante correspondiente a {refreshed.description}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            message.attach(f"comprobante-CM-{refreshed.id:06d}.pdf", pdf, "application/pdf")
            message.send(fail_silently=False)
        except Exception:
            logger.exception("No se pudo enviar el comprobante del movimiento %s", movement.pk)

    transaction.on_commit(_send)
    return True


def export_daily_account_close_csv(daily_close):
    if not isinstance(daily_close, DailyAccountClose):
        daily_close = DailyAccountClose.objects.select_related("account", "close_group").get(pk=daily_close)
    movements = CashMovement.objects.filter(account=daily_close.account, date_payment=daily_close.close_group.date).select_related(
        "code",
        "provider",
        "employee",
        "event",
        "service_type",
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fecha", "Cuenta", "Tipo", "Codigo", "Descripcion", "Importe", "Proveedor", "Empleado", "Evento", "Servicio", "Estado"])
    for movement in movements.order_by("id"):
        writer.writerow([
            movement.date_payment,
            movement.account.name,
            movement.movement_type,
            movement.code.code,
            movement.description,
            movement.amount,
            movement.provider.name if movement.provider_id else "",
            str(movement.employee) if movement.employee_id else "",
            movement.event.name if movement.event_id else "",
            movement.service_type.name if movement.service_type_id else "",
            movement.status,
        ])
    return output.getvalue()


@transaction.atomic
def close_daily_account(account, close_date, declared_balance, notes="", user=None):
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
    audit_log(user, "daily_account_close", daily_close)
    return daily_close


@transaction.atomic
def close_daily_cash_group(close_date, declared_balances=None, notes="", user=None):
    declared_balances = declared_balances or {}
    group, _ = DailyCashCloseGroup.objects.get_or_create(date=close_date)
    if group.status == DailyCashCloseGroup.Status.CLOSED:
        raise ValidationError("El cierre diario general ya esta cerrado.")

    for account in Account.objects.filter(active=True):
        declared_balance = declared_balances.get(str(account.id), calculate_account_balance(account, up_to_date=close_date))
        close_daily_account(account, close_date, declared_balance, user=user)

    group.notes = notes
    group.status = DailyCashCloseGroup.Status.CLOSED
    group.closed_at = timezone.now()
    group.save(update_fields=["notes", "status", "closed_at", "updated_at"])
    audit_log(user, "daily_cash_close", group)
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
    send_cash_movement_receipt_email(movement, provider.email)
    audit_log(user, "provider_payment", ledger)
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
    send_cash_movement_receipt_email(movement, employee.email)
    audit_log(user, "employee_payment", payment)
    return payment


@transaction.atomic
def register_service_payment(service_type, account, amount, payment_date=None, description="", payment_method="", user=None):
    if not isinstance(service_type, ServiceType):
        service_type = ServiceType.objects.get(pk=service_type)
    if not isinstance(account, Account):
        account = Account.objects.get(pk=account)
    payment_date = payment_date or timezone.localdate()
    ensure_account_day_is_open(account, payment_date)
    movement = CashMovement.objects.create(
        date_payment=payment_date,
        description=description or f"Pago de servicio - {service_type.name}",
        movement_type=CashMovement.MovementType.EXPENSE,
        amount=Decimal(str(amount)),
        account=account,
        code=get_code("SERVICIOS"),
        service_type=service_type,
        payment_method=payment_method,
        status=CashMovement.Status.CONFIRMED,
        created_by=user,
        updated_by=user,
    )
    send_cash_movement_receipt_email(movement)
    audit_log(user, "service_payment", movement)
    return movement


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
    send_cash_movement_receipt_email(movement)

    reminder = None
    if reminder_due_date or recurrence_type != Reminder.RecurrenceType.NONE:
        reminder = create_next_tax_reminder(
            tax_payment=tax_payment,
            due_date=reminder_due_date,
            recurrence_type=recurrence_type,
            remind_before_days=remind_before_days,
            custom_days=custom_days,
        )
    audit_log(user, "tax_payment", tax_payment)
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
