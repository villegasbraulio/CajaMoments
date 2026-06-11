import django_filters

from .models import CashMovement, ProviderLedgerEntry, Reminder


class CashMovementFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date_payment", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date_payment", lookup_expr="lte")
    account = django_filters.NumberFilter(field_name="account_id")
    movement_type = django_filters.CharFilter(field_name="movement_type")
    code = django_filters.NumberFilter(field_name="code_id")
    code_text = django_filters.CharFilter(field_name="code__code", lookup_expr="iexact")
    provider = django_filters.NumberFilter(field_name="provider_id")
    employee = django_filters.NumberFilter(field_name="employee_id")
    event = django_filters.NumberFilter(field_name="event_id")
    tax = django_filters.NumberFilter(field_name="tax_payment__tax_type_id")
    status = django_filters.CharFilter(field_name="status")

    class Meta:
        model = CashMovement
        fields = [
            "date_from",
            "date_to",
            "account",
            "movement_type",
            "code",
            "code_text",
            "provider",
            "employee",
            "event",
            "tax",
            "status",
        ]


class ProviderLedgerEntryFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = ProviderLedgerEntry
        fields = ["provider", "event", "entry_type", "date_from", "date_to"]


class ReminderFilter(django_filters.FilterSet):
    due_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Reminder
        fields = ["status", "recurrence_type", "due_from", "due_to"]
