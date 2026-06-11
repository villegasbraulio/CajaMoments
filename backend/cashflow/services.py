from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import (
    Account,
    AccountTransfer,
    CashMovement,
    DailyAccountClose,
    DailyCashCloseGroup,
    Employee,
    EmployeePayment,
    EventStaffAssignment,
    MovementCode,
    Provider,
    ProviderLedgerEntry,
    Reminder,
    TaxPayment,
    TaxType,
)


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
