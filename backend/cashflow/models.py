from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


MONEY_MAX_DIGITS = 14
MONEY_DECIMAL_PLACES = 2
MONEY_MIN = Decimal("0.01")


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Account(TimestampedModel):
    class AccountType(models.TextChoices):
        CASH = "CASH", "Efectivo"
        BANK = "BANK", "Banco"
        WALLET = "WALLET", "Billetera virtual"
        INVESTMENT = "INVESTMENT", "Inversion"
        FOREIGN_CURRENCY = "FOREIGN_CURRENCY", "Moneda extranjera"
        OTHER = "OTHER", "Otro"

    class Currency(models.TextChoices):
        ARS = "ARS", "ARS"
        USD = "USD", "USD"

    name = models.CharField(max_length=120, unique=True)
    type = models.CharField(max_length=30, choices=AccountType.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.ARS)
    active = models.BooleanField(default=True)
    initial_balance = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.currency})"

    def current_balance(self):
        totals = (
            self.cash_movements.filter(status=CashMovement.Status.CONFIRMED)
            .values("movement_type")
            .annotate(total=Sum("amount"))
        )
        balance = self.initial_balance
        for row in totals:
            amount = row["total"] or Decimal("0.00")
            if row["movement_type"] in (
                CashMovement.MovementType.INCOME,
                CashMovement.MovementType.TRANSFER_IN,
                CashMovement.MovementType.ADJUSTMENT,
            ):
                balance += amount
            elif row["movement_type"] in (
                CashMovement.MovementType.EXPENSE,
                CashMovement.MovementType.TRANSFER_OUT,
            ):
                balance -= amount
        return balance


class MovementCode(TimestampedModel):
    class MovementKind(models.TextChoices):
        INCOME = "INCOME", "Ingreso"
        EXPENSE = "EXPENSE", "Egreso"
        TRANSFER = "TRANSFER", "Transferencia"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"

    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    movement_type = models.CharField(max_length=20, choices=MovementKind.choices)
    category = models.CharField(max_length=80, blank=True)
    requires_provider = models.BooleanField(default=False)
    requires_employee = models.BooleanField(default=False)
    requires_tax = models.BooleanField(default=False)
    requires_event = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["category", "code"]

    def __str__(self):
        return self.code


class Provider(TimestampedModel):
    name = models.CharField(max_length=160, unique=True)
    category = models.CharField(max_length=120, blank=True)
    cuit = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=240, blank=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def balance(self):
        totals = self.ledger_entries.values("entry_type").annotate(total=Sum("amount"))
        balance = Decimal("0.00")
        for row in totals:
            amount = row["total"] or Decimal("0.00")
            if row["entry_type"] == ProviderLedgerEntry.EntryType.DEBT:
                balance += amount
            elif row["entry_type"] == ProviderLedgerEntry.EntryType.PAYMENT:
                balance -= amount
            else:
                balance += amount
        return balance


class EmployeeRole(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(TimestampedModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    alias = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=80, blank=True)
    document_number = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        unique_together = [("first_name", "last_name", "document_number")]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class Client(TimestampedModel):
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Presupuesto"
        SIGNALED = "SIGNALED", "Señado"
        CONFIRMED = "CONFIRMED", "Confirmado"
        DONE = "DONE", "Realizado"
        CLOSED = "CLOSED", "Cerrado"
        CANCELLED = "CANCELLED", "Cancelado"

    class Type(models.TextChoices):
        QUINCE = "QUINCE", "Cumpleaños de 15"
        EGRESADOS = "EGRESADOS", "Egresados"
        EVENTO_PRIVADO = "EVENTO_PRIVADO", "Evento privado"
        CASAMIENTO = "CASAMIENTO", "Casamiento"

    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    name = models.CharField(max_length=180)
    event_type = models.CharField(max_length=32, choices=Type.choices, default=Type.EVENTO_PRIVADO)
    event_date = models.DateField(null=True, blank=True)
    event_time = models.TimeField(null=True, blank=True)
    venue_space = models.CharField(max_length=160, blank=True)
    guest_count_dinner = models.PositiveIntegerField(null=True, blank=True)
    guest_count_toast = models.PositiveIntegerField(null=True, blank=True)
    main_table_notes = models.CharField(max_length=240, blank=True)
    tableware_notes = models.CharField(max_length=240, blank=True)
    protocol_notes = models.TextField(blank=True)
    beverage_notes = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)
    schedule_notes = models.TextField(blank=True)
    sketch = models.FileField(upload_to="event-sketches/", blank=True)
    function_notes = models.TextField(blank=True)
    operational_notes = models.TextField(blank=True)
    internal_status = models.CharField(max_length=120, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_phone = models.CharField(max_length=80, blank=True)
    contact_email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    public_payment_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_events",
    )
    closed_total_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
    )
    closed_paid_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
    )
    closed_pending_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
    )
    closed_expense_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
    )
    closed_result_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-event_date", "name"]

    def __str__(self):
        return self.name

    def client_display(self):
        return self.client.name if self.client_id else (self.contact_name or "")


class EventBudget(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        SENT = "SENT", "Enviado"
        APPROVED = "APPROVED", "Aprobado"
        CANCELLED = "CANCELLED", "Cancelado"

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="budget")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    optional_comments = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Presupuesto - {self.event}"

    def subtotal(self):
        return self.items.filter(is_optional=False).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    def optional_total(self):
        return self.items.filter(is_optional=True).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    def total(self):
        return self.items.aggregate(total=Sum("total"))["total"] or Decimal("0.00")


class EventBudgetItem(TimestampedModel):
    budget = models.ForeignKey(EventBudget, on_delete=models.CASCADE, related_name="items")
    service_name = models.CharField(max_length=180)
    category = models.CharField(max_length=120, blank=True)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    unit_label = models.CharField(max_length=40, blank=True)
    unit_price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_optional = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        quantity = self.quantity or Decimal("0.00")
        unit_price = self.unit_price or Decimal("0.00")
        self.total = quantity * unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service_name} - {self.budget.event}"


class EventBudgetPayment(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"
        CANCELLED = "cancelled", "Cancelado"
        REFUNDED = "refunded", "Reembolsado"
        IN_PROCESS = "in_process", "En proceso"

    class Purpose(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Seña"
        ADVANCE = "ADVANCE", "Adelanto"
        BUDGET_ITEM = "BUDGET_ITEM", "Servicio"

    budget = models.ForeignKey(EventBudget, on_delete=models.PROTECT, related_name="payments")
    budget_item = models.ForeignKey(EventBudgetItem, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    payment_purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.ADVANCE)
    idempotency_key = models.CharField(max_length=120, unique=True, default=uuid.uuid4)
    mp_preference_id = models.CharField(max_length=100, blank=True)
    preference_init_point = models.URLField(max_length=1000, blank=True)
    preference_sandbox_init_point = models.URLField(max_length=1000, blank=True)
    mp_payment_id = models.CharField(max_length=100, blank=True)
    mp_merchant_order_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    status_detail = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_type = models.CharField(max_length=50, blank=True)
    installments = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    currency = models.CharField(max_length=3, default=Account.Currency.ARS)
    receipt_email = models.EmailField(blank=True)
    cash_movement = models.OneToOneField(
        "CashMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="event_budget_payment",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["mp_preference_id"],
                condition=~models.Q(mp_preference_id=""),
                name="unique_event_budget_mp_preference",
            ),
            models.UniqueConstraint(
                fields=["mp_payment_id"],
                condition=~models.Q(mp_payment_id=""),
                name="unique_event_budget_mp_payment",
            ),
        ]

    def __str__(self):
        return f"{self.budget.event} - {self.status} - {self.amount}"


class GraduationEvent(TimestampedModel):
    event = models.OneToOneField(Event, on_delete=models.PROTECT, related_name="graduation")
    price_per_ticket = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    max_tickets_per_graduate = models.PositiveIntegerField(null=True, blank=True)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    active = models.BooleanField(default=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_graduation_events",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["event__event_date", "event__name"]

    def __str__(self):
        return f"Egresados - {self.event}"

    def paid_ticket_count(self):
        return self.purchases.filter(status=TicketPurchase.Status.PAID).aggregate(total=Sum("quantity"))["total"] or 0

    def current_ticket_price(self, on_date=None):
        on_date = on_date or timezone.localdate()
        price = self.ticket_prices.filter(valid_from__lte=on_date).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=on_date)
        ).order_by("-valid_from", "-id").first()
        return price.price if price else self.price_per_ticket


class GraduationTicketPrice(TimestampedModel):
    graduation_event = models.ForeignKey(GraduationEvent, on_delete=models.CASCADE, related_name="ticket_prices")
    price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-valid_from", "-id"]
        unique_together = [("graduation_event", "valid_from")]

    def __str__(self):
        return f"{self.graduation_event} - {self.valid_from} - {self.price}"

    def clean(self):
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError("La vigencia hasta no puede ser anterior a la vigencia desde.")


class Graduate(TimestampedModel):
    graduation_event = models.ForeignKey(GraduationEvent, on_delete=models.CASCADE, related_name="graduates")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        unique_together = [("graduation_event", "first_name", "last_name")]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        if self.graduation_event_id and self.graduation_event.closed_at:
            raise ValidationError("La lista de egresados ya esta cerrada.")


class TicketPurchase(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        IN_PROCESS = "in_process", "En proceso"
        PAID = "paid", "Pagado"
        CANCELLED = "cancelled", "Cancelado"
        REFUNDED = "refunded", "Reembolsado"

    graduation_event = models.ForeignKey(GraduationEvent, on_delete=models.PROTECT, related_name="purchases")
    graduate = models.ForeignKey(Graduate, on_delete=models.PROTECT, related_name="ticket_purchases")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    total_amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    email = models.EmailField()
    idempotency_key = models.CharField(max_length=120, unique=True, default=uuid.uuid4)
    mp_preference_id = models.CharField(max_length=100, blank=True)
    preference_init_point = models.URLField(max_length=1000, blank=True)
    preference_sandbox_init_point = models.URLField(max_length=1000, blank=True)
    mp_payment_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    status_detail = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_type = models.CharField(max_length=50, blank=True)
    cash_movement = models.OneToOneField(
        "CashMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ticket_purchase",
    )
    payment_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_purchases_created",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["mp_preference_id"],
                condition=~models.Q(mp_preference_id=""),
                name="unique_ticket_purchase_mp_preference",
            ),
            models.UniqueConstraint(
                fields=["mp_payment_id"],
                condition=~models.Q(mp_payment_id=""),
                name="unique_ticket_purchase_mp_payment",
            ),
        ]

    def save(self, *args, **kwargs):
        self.total_amount = self.graduation_event.current_ticket_price(self.payment_date) * Decimal(self.quantity or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.graduate} - {self.quantity} tarjetas"


class TicketPurchaseWebhookLog(models.Model):
    mp_notification_id = models.CharField(max_length=100)
    deduplication_key = models.CharField(max_length=64, unique=True)
    topic = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.topic} - {self.mp_notification_id}"


class ServiceType(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AuditLogEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries")
    action = models.CharField(max_length=80)
    model_name = models.CharField(max_length=120)
    object_id = models.CharField(max_length=80, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["model_name", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.created_at} {self.action} {self.model_name}#{self.object_id}"


class EventBudgetPaymentWebhookLog(models.Model):
    mp_notification_id = models.CharField(max_length=100)
    deduplication_key = models.CharField(max_length=64, unique=True)
    topic = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} - {self.mp_notification_id}"


class EventStaffAssignment(TimestampedModel):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planificado"
        WORKED = "WORKED", "Trabajado"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Parcialmente pagado"
        PAID = "PAID", "Pagado"
        CANCELLED = "CANCELLED", "Cancelado"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="staff_assignments")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="assignments")
    role = models.ForeignKey(EmployeeRole, on_delete=models.PROTECT, related_name="assignments")
    work_date = models.DateField()
    base_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    extra_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-work_date", "event", "employee"]

    def save(self, *args, **kwargs):
        self.total_amount = (self.base_amount or Decimal("0.00")) + (self.extra_amount or Decimal("0.00"))
        super().save(*args, **kwargs)

    def paid_amount(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    def pending_amount(self):
        return self.total_amount - self.paid_amount()

    def __str__(self):
        return f"{self.employee} - {self.event} - {self.role}"


class TaxType(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AccountTransfer(TimestampedModel):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmada"
        VOIDED = "VOIDED", "Anulada"

    date = models.DateField()
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="outgoing_transfers")
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="incoming_transfers")
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    fee_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    description = models.CharField(max_length=240)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)

    class Meta:
        ordering = ["-date", "-id"]

    def clean(self):
        if self.from_account_id and self.from_account_id == self.to_account_id:
            raise ValidationError("La cuenta de origen y destino no pueden ser la misma.")
        if self.from_account_id and self.to_account_id and self.from_account.currency != self.to_account.currency:
            raise ValidationError("No se permiten transferencias entre monedas distintas en Fase 1.")

    def __str__(self):
        return f"{self.from_account} -> {self.to_account} {self.amount}"


class TaxPayment(TimestampedModel):
    tax_type = models.ForeignKey(TaxType, on_delete=models.PROTECT, related_name="payments")
    period = models.CharField(max_length=80, blank=True)
    payment_date = models.DateField()
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="tax_payments")
    cash_movement = models.OneToOneField(
        "CashMovement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tax_payment_record",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "tax_type"]

    def __str__(self):
        return f"{self.tax_type} {self.period or self.payment_date}"


class CashMovement(TimestampedModel):
    class MovementType(models.TextChoices):
        INCOME = "INCOME", "Ingreso"
        EXPENSE = "EXPENSE", "Egreso"
        TRANSFER_IN = "TRANSFER_IN", "Transferencia entrante"
        TRANSFER_OUT = "TRANSFER_OUT", "Transferencia saliente"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        CONFIRMED = "CONFIRMED", "Confirmado"
        VOIDED = "VOIDED", "Anulado"

    date_invoice = models.DateField(null=True, blank=True)
    date_payment = models.DateField()
    description = models.CharField(max_length=240)
    voucher_number = models.CharField(max_length=80, blank=True)
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="cash_movements")
    code = models.ForeignKey(MovementCode, on_delete=models.PROTECT, related_name="cash_movements")
    service_type = models.ForeignKey(ServiceType, null=True, blank=True, on_delete=models.PROTECT, related_name="cash_movements")
    provider = models.ForeignKey(Provider, null=True, blank=True, on_delete=models.PROTECT, related_name="cash_movements")
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.PROTECT, related_name="cash_movements")
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.PROTECT, related_name="cash_movements")
    tax_payment = models.ForeignKey(TaxPayment, null=True, blank=True, on_delete=models.SET_NULL, related_name="cash_movements")
    transfer = models.ForeignKey(AccountTransfer, null=True, blank=True, on_delete=models.SET_NULL, related_name="cash_movements")
    payment_method = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cash_movements_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cash_movements_updated",
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cash_movements_voided",
    )
    void_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-date_payment", "-id"]
        indexes = [
            models.Index(fields=["date_payment", "account"]),
            models.Index(fields=["status", "movement_type"]),
        ]

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError("El importe debe ser mayor a cero.")
        self._validate_code_requirements()
        self._validate_closed_day()

    def _validate_code_requirements(self):
        if not self.code_id:
            return
        if self.code.requires_provider and not self.provider_id:
            raise ValidationError("Este codigo requiere proveedor.")
        if self.code.requires_employee and not self.employee_id:
            raise ValidationError("Este codigo requiere empleado.")
        if self.code.requires_tax and not (self.tax_payment_id or self.code.code == "IMPUESTOS"):
            raise ValidationError("Este codigo requiere impuesto.")
        if self.code.requires_event and not self.event_id:
            raise ValidationError("Este codigo requiere evento.")

    def _validate_closed_day(self):
        if not self.account_id or not self.date_payment:
            return
        exists_closed = DailyAccountClose.objects.filter(
            account_id=self.account_id,
            close_group__date=self.date_payment,
            closed_at__isnull=False,
        ).exists()
        if exists_closed:
            raise ValidationError("No se pueden crear o editar movimientos en una cuenta/dia cerrado.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("No se borran movimientos de caja. Use anulacion.")

    def signed_amount(self):
        if self.status != self.Status.CONFIRMED:
            return Decimal("0.00")
        if self.movement_type in (self.MovementType.INCOME, self.MovementType.TRANSFER_IN, self.MovementType.ADJUSTMENT):
            return self.amount
        return -self.amount

    def __str__(self):
        return f"{self.date_payment} {self.account} {self.description} {self.amount}"


class ProviderLedgerEntry(TimestampedModel):
    class EntryType(models.TextChoices):
        DEBT = "DEBT", "Deuda"
        PAYMENT = "PAYMENT", "Pago"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"

    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="ledger_entries")
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="provider_ledger_entries")
    date = models.DateField()
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    description = models.CharField(max_length=240)
    document_number = models.CharField(max_length=80, blank=True)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    cash_movement = models.OneToOneField(
        CashMovement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_ledger_entry",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def clean(self):
        if self.entry_type == self.EntryType.PAYMENT and self.cash_movement_id is None:
            raise ValidationError("Los pagos a proveedor desde caja deben asociarse a un movimiento de caja.")

    def __str__(self):
        return f"{self.provider} {self.entry_type} {self.amount}"


class EmployeePayment(TimestampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payments")
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="employee_payments")
    assignment = models.ForeignKey(
        EventStaffAssignment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    cash_movement = models.OneToOneField(CashMovement, on_delete=models.PROTECT, related_name="employee_payment")
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(MONEY_MIN)],
    )
    payment_date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return f"{self.employee} {self.amount}"


class DailyCashCloseGroup(TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierto"
        CLOSED = "Cerrado"

    date = models.DateField(unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def close(self):
        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at", "updated_at"])

    def __str__(self):
        return f"Cierre {self.date}"


class DailyAccountClose(TimestampedModel):
    close_group = models.ForeignKey(DailyCashCloseGroup, on_delete=models.CASCADE, related_name="account_closes")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="daily_closes")
    opening_balance = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    total_income = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=Decimal("0.00"))
    total_expense = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=Decimal("0.00"))
    total_transfer_in = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=Decimal("0.00"))
    total_transfer_out = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=Decimal("0.00"))
    total_adjustments = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=Decimal("0.00"))
    calculated_balance = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    declared_balance = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    difference = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    notes = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["close_group__date", "account__name"]
        unique_together = [("close_group", "account")]

    def __str__(self):
        return f"{self.close_group.date} - {self.account}"


class Reminder(TimestampedModel):
    class RecurrenceType(models.TextChoices):
        NONE = "NONE", "Sin recurrencia"
        MONTHLY = "MONTHLY", "Mensual"
        BIMONTHLY = "BIMONTHLY", "Bimestral"
        QUARTERLY = "QUARTERLY", "Trimestral"
        YEARLY = "YEARLY", "Anual"
        CUSTOM_DAYS = "CUSTOM_DAYS", "Dias personalizados"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        DONE = "DONE", "Hecho"
        CANCELLED = "CANCELLED", "Cancelado"

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    remind_before_days = models.PositiveIntegerField(default=0)
    recurrence_type = models.CharField(max_length=20, choices=RecurrenceType.choices, default=RecurrenceType.NONE)
    custom_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    related_tax_payment = models.ForeignKey(TaxPayment, null=True, blank=True, on_delete=models.SET_NULL, related_name="reminders")
    related_event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="reminders")
    related_provider = models.ForeignKey(Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="reminders")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "due_date"]

    def __str__(self):
        return self.title
