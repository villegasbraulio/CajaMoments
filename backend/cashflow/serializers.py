from rest_framework import serializers

from .models import (
    Account,
    AccountTransfer,
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
    EventStaffAssignment,
    MovementCode,
    Provider,
    ProviderLedgerEntry,
    Reminder,
    TaxPayment,
    TaxType,
)
from .services import calculate_account_balance


class AccountSerializer(serializers.ModelSerializer):
    current_balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = "__all__"

    def get_current_balance(self, obj):
        return calculate_account_balance(obj)


class MovementCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovementCode
        fields = "__all__"


class ProviderSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = "__all__"

    def get_balance(self, obj):
        return obj.balance()


class EmployeeRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeRole
        fields = "__all__"


class EmployeeSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = "__all__"

    def get_display_name(self, obj):
        return str(obj)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = "__all__"


class EventSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)
    client_email = serializers.CharField(source="client.email", read_only=True)
    client_notes = serializers.CharField(source="client.notes", read_only=True)
    guest_count_total = serializers.SerializerMethodField()
    display_contact = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = "__all__"

    def get_guest_count_total(self, obj):
        dinner = obj.guest_count_dinner or 0
        toast = obj.guest_count_toast or 0
        return max(dinner, toast)

    def get_display_contact(self, obj):
        return obj.client_display()


class EventBudgetItemSerializer(serializers.ModelSerializer):
    event_id = serializers.IntegerField(source="budget.event_id", read_only=True)
    event_name = serializers.CharField(source="budget.event.name", read_only=True)

    class Meta:
        model = EventBudgetItem
        fields = "__all__"
        read_only_fields = ["total"]


class EventBudgetPaymentSerializer(serializers.ModelSerializer):
    event_id = serializers.IntegerField(source="budget.event_id", read_only=True)
    event_name = serializers.CharField(source="budget.event.name", read_only=True)
    cash_movement_account = serializers.CharField(source="cash_movement.account.name", read_only=True)
    cash_movement_date = serializers.DateField(source="cash_movement.date_payment", read_only=True)

    class Meta:
        model = EventBudgetPayment
        fields = "__all__"
        read_only_fields = [
            "idempotency_key",
            "mp_preference_id",
            "preference_init_point",
            "preference_sandbox_init_point",
            "mp_payment_id",
            "mp_merchant_order_id",
            "status",
            "status_detail",
            "payment_method",
            "payment_type",
            "installments",
            "amount",
            "currency",
            "cash_movement",
            "cash_movement_account",
            "cash_movement_date",
        ]


class EventBudgetSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source="event.name", read_only=True)
    item_count = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    optional_total = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    items = EventBudgetItemSerializer(many=True, read_only=True)
    latest_payment = serializers.SerializerMethodField()

    class Meta:
        model = EventBudget
        fields = "__all__"

    def get_item_count(self, obj):
        return obj.items.count()

    def get_subtotal(self, obj):
        return obj.subtotal()

    def get_optional_total(self, obj):
        return obj.optional_total()

    def get_grand_total(self, obj):
        return obj.total()

    def get_latest_payment(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        return EventBudgetPaymentSerializer(payment).data if payment else None


class EventStaffAssignmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    role_name = serializers.CharField(source="role.name", read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)
    paid_amount = serializers.SerializerMethodField()
    pending_amount = serializers.SerializerMethodField()

    class Meta:
        model = EventStaffAssignment
        fields = "__all__"
        read_only_fields = ["total_amount"]

    def get_paid_amount(self, obj):
        return obj.paid_amount()

    def get_pending_amount(self, obj):
        return obj.pending_amount()

    def get_employee_name(self, obj):
        return str(obj.employee)


class TaxTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxType
        fields = "__all__"


class CashMovementSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    code_name = serializers.CharField(source="code.name", read_only=True)
    code_code = serializers.CharField(source="code.code", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    employee_name = serializers.SerializerMethodField()
    event_name = serializers.CharField(source="event.name", read_only=True)

    class Meta:
        model = CashMovement
        fields = "__all__"
        read_only_fields = ["created_by", "updated_by", "voided_by", "void_reason"]

    def get_employee_name(self, obj):
        return str(obj.employee) if obj.employee_id else ""


class AccountTransferSerializer(serializers.ModelSerializer):
    from_account_name = serializers.CharField(source="from_account.name", read_only=True)
    to_account_name = serializers.CharField(source="to_account.name", read_only=True)

    class Meta:
        model = AccountTransfer
        fields = "__all__"


class DailyAccountCloseSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)
    currency = serializers.CharField(source="account.currency", read_only=True)

    class Meta:
        model = DailyAccountClose
        fields = "__all__"


class DailyCashCloseGroupSerializer(serializers.ModelSerializer):
    account_closes = DailyAccountCloseSerializer(many=True, read_only=True)

    class Meta:
        model = DailyCashCloseGroup
        fields = "__all__"


class ProviderLedgerEntrySerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)

    class Meta:
        model = ProviderLedgerEntry
        fields = "__all__"


class EmployeePaymentSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    event_name = serializers.CharField(source="event.name", read_only=True)

    class Meta:
        model = EmployeePayment
        fields = "__all__"
        read_only_fields = ["cash_movement"]

    def get_employee_name(self, obj):
        return str(obj.employee)


class TaxPaymentSerializer(serializers.ModelSerializer):
    tax_type_name = serializers.CharField(source="tax_type.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = TaxPayment
        fields = "__all__"
        read_only_fields = ["cash_movement"]


class ReminderSerializer(serializers.ModelSerializer):
    tax_type_name = serializers.CharField(source="related_tax_payment.tax_type.name", read_only=True)
    event_name = serializers.CharField(source="related_event.name", read_only=True)
    provider_name = serializers.CharField(source="related_provider.name", read_only=True)

    class Meta:
        model = Reminder
        fields = "__all__"


class DashboardSerializer(serializers.Serializer):
    date = serializers.DateField()
    accounts = serializers.ListField()
    balances_by_currency = serializers.ListField()
    today_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_reminders = ReminderSerializer(many=True)
    pending_account_closes = serializers.ListField()
    today_close_differences = serializers.ListField()
    providers_with_credit = serializers.ListField()
    employee_pending = serializers.ListField()
    voided_count = serializers.IntegerField()
