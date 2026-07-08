from django.contrib import admin, messages
from django.core.exceptions import ValidationError

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
    EmployeeRole,
    Event,
    EventBudget,
    EventBudgetItem,
    EventBudgetPayment,
    EventBudgetPaymentWebhookLog,
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
    TicketPurchaseWebhookLog,
    TaxType,
)
from .services import void_cash_movement


class AuditReadonlyMixin:
    readonly_fields = ("created_at", "updated_at")


@admin.register(Account)
class AccountAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "type", "currency", "initial_balance", "active", "updated_at")
    search_fields = ("name", "notes")
    list_filter = ("type", "currency", "active")


@admin.register(MovementCode)
class MovementCodeAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("code", "name", "movement_type", "category", "active")
    search_fields = ("code", "name", "category")
    list_filter = ("movement_type", "category", "active", "requires_provider", "requires_employee", "requires_tax", "requires_event")


@admin.register(CashMovement)
class CashMovementAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("date_payment", "account", "movement_type", "code", "amount", "status", "provider", "employee", "event")
    search_fields = ("description", "voucher_number", "notes", "provider__name", "employee__first_name", "employee__last_name", "event__name")
    list_filter = ("status", "movement_type", "account", "code", "date_payment")
    readonly_fields = AuditReadonlyMixin.readonly_fields + ("created_by", "updated_by", "voided_by", "void_reason")
    actions = ("void_selected",)

    @admin.action(description="Anular movimientos seleccionados")
    def void_selected(self, request, queryset):
        count = 0
        for movement in queryset:
            try:
                void_cash_movement(movement, "Anulado desde admin", request.user)
                count += 1
            except ValidationError as exc:
                self.message_user(request, f"No se pudo anular {movement.id}: {exc}", level=messages.ERROR)
        if count:
            self.message_user(request, f"Movimientos anulados: {count}", level=messages.SUCCESS)


@admin.register(AccountTransfer)
class AccountTransferAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("date", "from_account", "to_account", "amount", "fee_amount", "status")
    search_fields = ("description",)
    list_filter = ("status", "from_account", "to_account", "date")


@admin.register(DailyCashCloseGroup)
class DailyCashCloseGroupAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("date", "status", "closed_at")
    search_fields = ("notes",)
    list_filter = ("status", "date")
    readonly_fields = AuditReadonlyMixin.readonly_fields + ("closed_at",)


@admin.register(DailyAccountClose)
class DailyAccountCloseAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("close_group", "account", "calculated_balance", "declared_balance", "difference", "closed_at")
    search_fields = ("account__name", "notes")
    list_filter = ("account", "close_group__date")
    readonly_fields = AuditReadonlyMixin.readonly_fields + ("closed_at",)


@admin.register(Provider)
class ProviderAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "category", "cuit", "phone", "active")
    search_fields = ("name", "category", "cuit", "phone", "email")
    list_filter = ("category", "active")


@admin.register(ProviderLedgerEntry)
class ProviderLedgerEntryAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("date", "provider", "entry_type", "amount", "event", "cash_movement")
    search_fields = ("provider__name", "description", "document_number", "notes")
    list_filter = ("entry_type", "provider", "date")


@admin.register(Employee)
class EmployeeAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("last_name", "first_name", "alias", "phone", "active")
    search_fields = ("first_name", "last_name", "alias", "phone", "document_number")
    list_filter = ("active",)


@admin.register(EmployeeRole)
class EmployeeRoleAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "active")
    search_fields = ("name",)
    list_filter = ("active",)


@admin.register(Client)
class ClientAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "phone", "email")
    search_fields = ("name", "phone", "email")


@admin.register(Event)
class EventAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "client", "event_type", "event_date", "event_time", "venue_space", "status", "internal_status")
    search_fields = ("name", "client__name", "event_type", "notes", "venue_space", "contact_name", "contact_phone", "internal_status")
    list_filter = ("status", "event_type", "event_date", "internal_status")


@admin.register(EventBudget)
class EventBudgetAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("event", "status", "updated_at")
    search_fields = ("event__name", "event__client__name", "notes", "optional_comments", "internal_notes")
    list_filter = ("status",)


@admin.register(EventBudgetItem)
class EventBudgetItemAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("service_name", "budget", "category", "quantity", "unit_price", "total", "is_optional", "sort_order")
    search_fields = ("service_name", "category", "notes", "budget__event__name")
    list_filter = ("category", "is_optional")


@admin.register(EventBudgetPayment)
class EventBudgetPaymentAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("budget", "payment_purpose", "status", "amount", "currency", "cash_movement", "mp_preference_id", "mp_payment_id", "updated_at")
    search_fields = ("budget__event__name", "mp_preference_id", "mp_payment_id", "status_detail")
    list_filter = ("payment_purpose", "status", "currency")
    readonly_fields = AuditReadonlyMixin.readonly_fields + (
        "idempotency_key",
        "mp_preference_id",
        "preference_init_point",
        "preference_sandbox_init_point",
        "mp_payment_id",
        "mp_merchant_order_id",
        "cash_movement",
    )


@admin.register(EventBudgetPaymentWebhookLog)
class EventBudgetPaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("topic", "mp_notification_id", "processed", "received_at")
    search_fields = ("mp_notification_id", "deduplication_key", "error")
    list_filter = ("topic", "processed", "received_at")
    readonly_fields = ("mp_notification_id", "deduplication_key", "topic", "payload", "processed", "error", "received_at")


@admin.register(EventStaffAssignment)
class EventStaffAssignmentAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("event", "employee", "role", "work_date", "total_amount", "status")
    search_fields = ("event__name", "employee__first_name", "employee__last_name", "employee__alias", "role__name")
    list_filter = ("status", "role", "work_date")


@admin.register(GraduationEvent)
class GraduationEventAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("event", "price_per_ticket", "capacity", "max_tickets_per_graduate", "paid_ticket_count", "active", "closed_at", "public_token")
    search_fields = ("event__name", "event__client__name", "notes")
    list_filter = ("active", "closed_at")
    readonly_fields = AuditReadonlyMixin.readonly_fields + ("public_token", "closed_at", "closed_by")


@admin.register(GraduationTicketPrice)
class GraduationTicketPriceAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("graduation_event", "valid_from", "valid_until", "price")
    search_fields = ("graduation_event__event__name", "notes")
    list_filter = ("valid_from", "valid_until")


@admin.register(Graduate)
class GraduateAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("last_name", "first_name", "graduation_event")
    search_fields = ("first_name", "last_name", "notes", "graduation_event__event__name")
    list_filter = ("graduation_event",)


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("created_at", "graduation_event", "graduate", "quantity", "total_amount", "email", "status", "cash_movement")
    search_fields = ("graduate__first_name", "graduate__last_name", "email", "mp_preference_id", "mp_payment_id")
    list_filter = ("status", "graduation_event")
    readonly_fields = AuditReadonlyMixin.readonly_fields + (
        "total_amount",
        "idempotency_key",
        "mp_preference_id",
        "preference_init_point",
        "preference_sandbox_init_point",
        "mp_payment_id",
        "cash_movement",
    )


@admin.register(TicketPurchaseWebhookLog)
class TicketPurchaseWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("topic", "mp_notification_id", "processed", "received_at")
    search_fields = ("mp_notification_id", "deduplication_key", "error")
    list_filter = ("topic", "processed", "received_at")
    readonly_fields = ("mp_notification_id", "deduplication_key", "topic", "payload", "processed", "error", "received_at")


@admin.register(ServiceType)
class ServiceTypeAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "active")
    search_fields = ("name", "description")
    list_filter = ("active",)


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "model_name", "object_id")
    search_fields = ("action", "model_name", "object_id", "detail", "user__username")
    list_filter = ("action", "model_name", "created_at")
    readonly_fields = ("user", "action", "model_name", "object_id", "detail", "created_at")


@admin.register(EmployeePayment)
class EmployeePaymentAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("payment_date", "employee", "event", "assignment", "amount", "cash_movement")
    search_fields = ("employee__first_name", "employee__last_name", "employee__alias", "notes")
    list_filter = ("payment_date", "employee", "event")


@admin.register(TaxType)
class TaxTypeAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("name", "active")
    search_fields = ("name", "description")
    list_filter = ("active",)


@admin.register(TaxPayment)
class TaxPaymentAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("payment_date", "tax_type", "period", "account", "amount", "cash_movement")
    search_fields = ("tax_type__name", "period", "notes")
    list_filter = ("tax_type", "account", "payment_date")


@admin.register(Reminder)
class ReminderAdmin(AuditReadonlyMixin, admin.ModelAdmin):
    list_display = ("due_date", "title", "status", "recurrence_type", "related_tax_payment", "related_event", "related_provider")
    search_fields = ("title", "description")
    list_filter = ("status", "recurrence_type", "due_date")
    readonly_fields = AuditReadonlyMixin.readonly_fields + ("completed_at",)
