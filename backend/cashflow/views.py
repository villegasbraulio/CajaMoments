from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import CashMovementFilter, ProviderLedgerEntryFilter, ReminderFilter
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
    EventBudgetPaymentWebhookLog,
    EventStaffAssignment,
    MovementCode,
    Provider,
    ProviderLedgerEntry,
    Reminder,
    TaxPayment,
    TaxType,
)
from .serializers import (
    AccountSerializer,
    AccountTransferSerializer,
    CashMovementSerializer,
    ClientSerializer,
    DailyAccountCloseSerializer,
    DailyCashCloseGroupSerializer,
    DashboardSerializer,
    EmployeePaymentSerializer,
    EmployeeRoleSerializer,
    EmployeeSerializer,
    EventSerializer,
    EventBudgetItemSerializer,
    EventBudgetPaymentSerializer,
    EventBudgetSerializer,
    EventStaffAssignmentSerializer,
    MovementCodeSerializer,
    ProviderLedgerEntrySerializer,
    ProviderSerializer,
    ReminderSerializer,
    TaxPaymentSerializer,
    TaxTypeSerializer,
)
from .services import (
    calculate_account_balance,
    close_daily_account,
    close_daily_cash_group,
    create_account_transfer,
    create_balance_adjustment,
    create_event_budget_payment_preference,
    build_mp_webhook_deduplication_key,
    get_dashboard_summary,
    get_or_create_event_budget,
    get_event_overview,
    has_valid_mp_signature,
    MercadoPagoAPIError,
    MercadoPagoClient,
    PaymentIntegrityError,
    register_employee_payment,
    register_provider_payment,
    register_tax_payment,
    sync_event_budget_payment,
    void_cash_movement,
)


def request_user_or_none(request):
    return request.user if request.user and request.user.is_authenticated else None


def parse_decimal(value, default=None):
    if value is None or value == "":
        return default
    return Decimal(str(value))


def parse_date(value, default=None):
    if not value:
        return default
    return timezone.datetime.strptime(value, "%Y-%m-%d").date()


def validation_error_response(exc):
    if hasattr(exc, "message_dict"):
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    search_fields = ["name", "notes"]
    ordering_fields = ["name", "type", "currency"]

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        account = self.get_object()
        up_to_date = parse_date(request.query_params.get("up_to_date"))
        return Response({"balance": calculate_account_balance(account, up_to_date=up_to_date)})

    @action(detail=True, methods=["post"], url_path="adjust-balance")
    def adjust_balance(self, request, pk=None):
        try:
            movement = create_balance_adjustment(
                account=self.get_object(),
                declared_balance=request.data.get("declared_balance"),
                movement_date=parse_date(request.data.get("date"), timezone.localdate()),
                description=request.data.get("description", ""),
                user=request_user_or_none(request),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        if movement is None:
            return Response({"detail": "El saldo declarado coincide con el calculado. No se creo ajuste."})
        return Response(CashMovementSerializer(movement).data, status=status.HTTP_201_CREATED)


class MovementCodeViewSet(viewsets.ModelViewSet):
    queryset = MovementCode.objects.all()
    serializer_class = MovementCodeSerializer
    search_fields = ["code", "name", "category"]
    ordering_fields = ["code", "name", "category"]


class CashMovementViewSet(viewsets.ModelViewSet):
    queryset = CashMovement.objects.select_related(
        "account",
        "code",
        "provider",
        "employee",
        "event",
        "tax_payment",
        "transfer",
    )
    serializer_class = CashMovementSerializer
    filterset_class = CashMovementFilter
    search_fields = ["description", "voucher_number", "notes"]
    ordering_fields = ["date_payment", "amount", "created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=request_user_or_none(self.request), updated_by=request_user_or_none(self.request))

    def perform_update(self, serializer):
        serializer.save(updated_by=request_user_or_none(self.request))

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        try:
            movement = void_cash_movement(
                self.get_object(),
                reason=request.data.get("reason", ""),
                user=request_user_or_none(request),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(CashMovementSerializer(movement).data)


class AccountTransferViewSet(viewsets.ModelViewSet):
    queryset = AccountTransfer.objects.select_related("from_account", "to_account")
    serializer_class = AccountTransferSerializer
    search_fields = ["description"]
    ordering_fields = ["date", "amount"]

    def create(self, request, *args, **kwargs):
        try:
            transfer = create_account_transfer(
                from_account=request.data.get("from_account"),
                to_account=request.data.get("to_account"),
                amount=request.data.get("amount"),
                transfer_date=parse_date(request.data.get("date"), timezone.localdate()),
                fee_amount=parse_decimal(request.data.get("fee_amount"), Decimal("0.00")),
                description=request.data.get("description", "Transferencia entre cuentas"),
                user=request_user_or_none(request),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(self.get_serializer(transfer).data, status=status.HTTP_201_CREATED)


class DailyCashCloseGroupViewSet(viewsets.ModelViewSet):
    queryset = DailyCashCloseGroup.objects.prefetch_related("account_closes__account")
    serializer_class = DailyCashCloseGroupSerializer
    filterset_fields = ["date", "status"]
    ordering_fields = ["date", "status"]

    def create(self, request, *args, **kwargs):
        try:
            group = close_daily_cash_group(
                close_date=parse_date(request.data.get("date"), timezone.localdate()),
                declared_balances=request.data.get("declared_balances", {}),
                notes=request.data.get("notes", ""),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(self.get_serializer(group).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="close-account")
    def close_account(self, request):
        account = get_object_or_404(Account, pk=request.data.get("account"))
        try:
            daily_close = close_daily_account(
                account=account,
                close_date=parse_date(request.data.get("date"), timezone.localdate()),
                declared_balance=request.data.get("declared_balance"),
                notes=request.data.get("notes", ""),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(DailyAccountCloseSerializer(daily_close).data, status=status.HTTP_201_CREATED)


class DailyAccountCloseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyAccountClose.objects.select_related("close_group", "account")
    serializer_class = DailyAccountCloseSerializer
    filterset_fields = ["close_group__date", "account", "account__currency"]
    ordering_fields = ["close_group__date", "account__name"]


class ProviderViewSet(viewsets.ModelViewSet):
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    search_fields = ["name", "category", "cuit", "phone", "email"]
    ordering_fields = ["name", "category"]

    @action(detail=True, methods=["get"])
    def ledger(self, request, pk=None):
        entries = self.get_object().ledger_entries.select_related("event", "cash_movement")
        return Response(ProviderLedgerEntrySerializer(entries, many=True).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        event = None
        if request.data.get("event"):
            event = get_object_or_404(Event, pk=request.data.get("event"))
        try:
            entry = register_provider_payment(
                provider=self.get_object(),
                account=request.data.get("account"),
                amount=request.data.get("amount"),
                payment_date=parse_date(request.data.get("date"), timezone.localdate()),
                event=event,
                description=request.data.get("description", ""),
                document_number=request.data.get("document_number", ""),
                user=request_user_or_none(request),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(ProviderLedgerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class ProviderLedgerEntryViewSet(viewsets.ModelViewSet):
    queryset = ProviderLedgerEntry.objects.select_related("provider", "event", "cash_movement")
    serializer_class = ProviderLedgerEntrySerializer
    filterset_class = ProviderLedgerEntryFilter
    search_fields = ["description", "document_number", "notes"]
    ordering_fields = ["date", "amount", "created_at"]


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    search_fields = ["first_name", "last_name", "alias", "phone", "document_number"]
    ordering_fields = ["last_name", "first_name", "alias"]


class EmployeeRoleViewSet(viewsets.ModelViewSet):
    queryset = EmployeeRole.objects.all()
    serializer_class = EmployeeRoleSerializer
    search_fields = ["name"]
    ordering_fields = ["name"]


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    search_fields = ["name", "phone", "email"]
    ordering_fields = ["name"]


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.select_related("client")
    serializer_class = EventSerializer
    filterset_fields = ["status", "event_date", "client", "event_type", "internal_status"]
    search_fields = [
        "name",
        "event_type",
        "notes",
        "client__name",
        "venue_space",
        "contact_name",
        "contact_phone",
        "internal_status",
    ]
    ordering_fields = ["event_date", "event_time", "name", "status", "client__name"]

    @action(detail=True, methods=["get"])
    def overview(self, request, pk=None):
        event = self.get_object()
        overview = get_event_overview(event)
        return Response(
            {
                "event": self.get_serializer(event).data,
                "linked_counts": overview["linked_counts"],
                "financial": overview["financial"],
                "service_snapshot": overview["service_snapshot"],
                "budget_summary": overview["budget_summary"],
            }
        )

    @action(detail=True, methods=["get"], url_path="budget")
    def budget(self, request, pk=None):
        budget = get_or_create_event_budget(self.get_object())
        return Response(EventBudgetSerializer(budget).data)


class EventBudgetViewSet(viewsets.ModelViewSet):
    queryset = EventBudget.objects.select_related("event", "event__client")
    serializer_class = EventBudgetSerializer
    filterset_fields = ["event", "status"]
    search_fields = ["event__name", "event__client__name", "notes", "optional_comments", "internal_notes"]
    ordering_fields = ["updated_at", "created_at", "event__event_date"]


class EventBudgetItemViewSet(viewsets.ModelViewSet):
    queryset = EventBudgetItem.objects.select_related("budget", "budget__event")
    serializer_class = EventBudgetItemSerializer
    filterset_fields = ["budget", "budget__event", "category", "is_optional"]
    search_fields = ["service_name", "category", "notes", "budget__event__name"]
    ordering_fields = ["sort_order", "service_name", "total", "created_at"]


class EventBudgetPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EventBudgetPayment.objects.select_related("budget", "budget__event", "cash_movement", "cash_movement__account")
    serializer_class = EventBudgetPaymentSerializer
    filterset_fields = ["budget", "budget__event", "status", "currency"]
    search_fields = ["budget__event__name", "mp_preference_id", "mp_payment_id", "status_detail"]
    ordering_fields = ["created_at", "updated_at", "amount", "status"]


class EventBudgetPaymentPreferenceAPIView(APIView):
    def post(self, request):
        budget = get_object_or_404(EventBudget, pk=request.data.get("budget"))
        try:
            payment = create_event_budget_payment_preference(budget)
        except ValidationError as exc:
            return validation_error_response(exc)
        except MercadoPagoAPIError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        payload = EventBudgetPaymentSerializer(payment).data
        payload["preference_id"] = payment.mp_preference_id
        payload["init_point"] = payment.preference_init_point or None
        payload["sandbox_init_point"] = payment.preference_sandbox_init_point or None
        return Response(payload, status=status.HTTP_201_CREATED)


class EventBudgetPaymentWebhookAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        topic = str(
            request.query_params.get("type")
            or request.query_params.get("topic")
            or payload.get("type")
            or payload.get("topic")
            or ""
        )
        notification_id = str(
            payload.get("id")
            or request.query_params.get("id")
            or request.query_params.get("data.id")
            or (payload.get("data") or {}).get("id")
            or "unknown"
        )
        payment_resource_id = request.query_params.get("data.id") or str((payload.get("data") or {}).get("id") or "")
        if not payment_resource_id and topic == "payment":
            payment_resource_id = str(request.query_params.get("id") or payload.get("id") or "")
        deduplication_key = build_mp_webhook_deduplication_key(topic or "unknown", notification_id, payment_resource_id, payload)
        webhook_log, created = EventBudgetPaymentWebhookLog.objects.get_or_create(
            deduplication_key=deduplication_key,
            defaults={"mp_notification_id": notification_id, "topic": topic or "unknown", "payload": payload},
        )
        if not created and webhook_log.processed:
            return Response(status=status.HTTP_200_OK)
        if not has_valid_mp_signature(request, payload):
            webhook_log.error = "invalid_signature"
            webhook_log.save(update_fields=["error"])
            return Response(status=status.HTTP_403_FORBIDDEN)
        if topic != "payment":
            webhook_log.processed = True
            webhook_log.save(update_fields=["processed"])
            return Response(status=status.HTTP_200_OK)
        if not payment_resource_id:
            webhook_log.error = "missing_payment_id"
            webhook_log.save(update_fields=["error"])
            return Response(status=status.HTTP_200_OK)
        try:
            payment_data = MercadoPagoClient().get_payment(str(payment_resource_id))
            payment = self._find_payment(payment_data)
            if payment is None:
                webhook_log.error = "payment_not_found"
                webhook_log.save(update_fields=["error"])
                return Response(status=status.HTTP_200_OK)
            sync_event_budget_payment(payment.id, payment_data)
            webhook_log.processed = True
            webhook_log.error = ""
            webhook_log.save(update_fields=["processed", "error"])
        except PaymentIntegrityError as exc:
            if "payment" in locals():
                EventBudgetPayment.objects.filter(pk=payment.pk).update(status_detail="integrity_validation_failed")
            webhook_log.error = f"payment_integrity_error: {exc}"
            webhook_log.processed = True
            webhook_log.save(update_fields=["error", "processed"])
        except MercadoPagoAPIError as exc:
            webhook_log.error = str(exc)
            webhook_log.save(update_fields=["error"])
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(status=status.HTTP_200_OK)

    def _find_payment(self, payment_data):
        external_reference = str(payment_data.get("external_reference") or "")
        if external_reference.startswith("event-budget-payment:"):
            return EventBudgetPayment.objects.filter(pk=external_reference.rsplit(":", 1)[-1]).first()
        metadata = payment_data.get("metadata") or {}
        payment_id = metadata.get("event_budget_payment_id")
        if payment_id:
            return EventBudgetPayment.objects.filter(pk=payment_id).first()
        preference_id = str(metadata.get("preference_id") or "")
        if preference_id:
            return EventBudgetPayment.objects.filter(mp_preference_id=preference_id).first()
        return None


class EventStaffAssignmentViewSet(viewsets.ModelViewSet):
    queryset = EventStaffAssignment.objects.select_related("event", "employee", "role")
    serializer_class = EventStaffAssignmentSerializer
    filterset_fields = ["event", "employee", "role", "status", "work_date"]
    search_fields = ["event__name", "employee__first_name", "employee__last_name", "employee__alias", "role__name"]
    ordering_fields = ["work_date", "total_amount", "status"]


class EmployeePaymentViewSet(viewsets.ModelViewSet):
    queryset = EmployeePayment.objects.select_related("employee", "event", "assignment", "cash_movement")
    serializer_class = EmployeePaymentSerializer
    filterset_fields = ["employee", "event", "assignment", "payment_date"]
    ordering_fields = ["payment_date", "amount"]

    def create(self, request, *args, **kwargs):
        event = None
        if request.data.get("event"):
            event = get_object_or_404(Event, pk=request.data.get("event"))
        try:
            payment = register_employee_payment(
                employee=request.data.get("employee"),
                account=request.data.get("account"),
                amount=request.data.get("amount"),
                payment_date=parse_date(request.data.get("payment_date"), timezone.localdate()),
                assignment=request.data.get("assignment"),
                event=event,
                notes=request.data.get("notes", ""),
                user=request_user_or_none(request),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(self.get_serializer(payment).data, status=status.HTTP_201_CREATED)


class TaxTypeViewSet(viewsets.ModelViewSet):
    queryset = TaxType.objects.all()
    serializer_class = TaxTypeSerializer
    search_fields = ["name", "description"]
    ordering_fields = ["name"]


class TaxPaymentViewSet(viewsets.ModelViewSet):
    queryset = TaxPayment.objects.select_related("tax_type", "account", "cash_movement")
    serializer_class = TaxPaymentSerializer
    filterset_fields = ["tax_type", "account", "payment_date", "period"]
    search_fields = ["period", "notes", "tax_type__name"]
    ordering_fields = ["payment_date", "amount"]

    def create(self, request, *args, **kwargs):
        try:
            tax_payment, _reminder = register_tax_payment(
                tax_type=request.data.get("tax_type"),
                account=request.data.get("account"),
                amount=request.data.get("amount"),
                payment_date=parse_date(request.data.get("payment_date"), timezone.localdate()),
                period=request.data.get("period", ""),
                notes=request.data.get("notes", ""),
                reminder_due_date=parse_date(request.data.get("reminder_due_date")),
                recurrence_type=request.data.get("recurrence_type", Reminder.RecurrenceType.NONE),
                remind_before_days=int(request.data.get("remind_before_days") or 0),
                custom_days=request.data.get("custom_days"),
                user=request_user_or_none(request),
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        return Response(self.get_serializer(tax_payment).data, status=status.HTTP_201_CREATED)


class ReminderViewSet(viewsets.ModelViewSet):
    queryset = Reminder.objects.select_related("related_tax_payment__tax_type", "related_event", "related_provider")
    serializer_class = ReminderSerializer
    filterset_class = ReminderFilter
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "status", "created_at"]

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        reminder = self.get_object()
        reminder.status = Reminder.Status.DONE
        reminder.completed_at = timezone.now()
        reminder.save(update_fields=["status", "completed_at", "updated_at"])
        return Response(self.get_serializer(reminder).data)


class DashboardAPIView(APIView):
    def get(self, request):
        summary = get_dashboard_summary(parse_date(request.query_params.get("date"), timezone.localdate()))
        return Response(DashboardSerializer(summary).data)


class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"detail": "Usuario o contrasena invalidos."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "is_superuser": user.is_superuser,
                },
            }
        )


class AuthStatusAPIView(APIView):
    def get(self, request):
        return Response(
            {
                "user": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "is_superuser": request.user.is_superuser,
                }
            }
        )


class LogoutAPIView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportsViewSet(viewsets.ViewSet):
    def _period(self, request):
        date_from = parse_date(request.query_params.get("date_from"), timezone.localdate().replace(day=1))
        date_to = parse_date(request.query_params.get("date_to"), timezone.localdate())
        return date_from, date_to

    @action(detail=False, methods=["get"], url_path="daily-cash-summary")
    def daily_cash_summary(self, request):
        report_date = parse_date(request.query_params.get("date"), timezone.localdate())
        closes = DailyAccountClose.objects.filter(close_group__date=report_date).select_related("account", "close_group")
        movements = CashMovement.objects.filter(date_payment=report_date, status=CashMovement.Status.CONFIRMED)
        return Response(
            {
                "date": report_date,
                "account_closes": DailyAccountCloseSerializer(closes, many=True).data,
                "income": movements.filter(movement_type=CashMovement.MovementType.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
                "expense": movements.filter(movement_type=CashMovement.MovementType.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
            }
        )

    @action(detail=False, methods=["get"], url_path="account-balances")
    def account_balances(self, request):
        up_to_date = parse_date(request.query_params.get("date"), timezone.localdate())
        return Response(
            [
                {
                    "id": account.id,
                    "name": account.name,
                    "currency": account.currency,
                    "type": account.type,
                    "balance": calculate_account_balance(account, up_to_date=up_to_date),
                }
                for account in Account.objects.filter(active=True)
            ]
        )

    @action(detail=False, methods=["get"], url_path="income-vs-expense")
    def income_vs_expense(self, request):
        date_from, date_to = self._period(request)
        movements = CashMovement.objects.filter(
            date_payment__gte=date_from,
            date_payment__lte=date_to,
            status=CashMovement.Status.CONFIRMED,
        )
        return Response(
            {
                "date_from": date_from,
                "date_to": date_to,
                "income": movements.filter(movement_type=CashMovement.MovementType.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
                "expense": movements.filter(movement_type=CashMovement.MovementType.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
            }
        )

    @action(detail=False, methods=["get"], url_path="expense-by-code")
    def expense_by_code(self, request):
        date_from, date_to = self._period(request)
        rows = (
            CashMovement.objects.filter(
                date_payment__gte=date_from,
                date_payment__lte=date_to,
                status=CashMovement.Status.CONFIRMED,
                movement_type=CashMovement.MovementType.EXPENSE,
            )
            .values("code__code", "code__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )
        return Response(list(rows))

    @action(detail=False, methods=["get"], url_path="provider-expenses")
    def provider_expenses(self, request):
        date_from, date_to = self._period(request)
        rows = (
            CashMovement.objects.filter(
                date_payment__gte=date_from,
                date_payment__lte=date_to,
                status=CashMovement.Status.CONFIRMED,
                provider__isnull=False,
            )
            .values("provider_id", "provider__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )
        return Response(list(rows))

    @action(detail=False, methods=["get"], url_path="provider-balances")
    def provider_balances(self, request):
        return Response([{"id": provider.id, "name": provider.name, "balance": provider.balance()} for provider in Provider.objects.all()])

    @action(detail=False, methods=["get"], url_path="providers-with-credit")
    def providers_with_credit(self, request):
        rows = [{"id": provider.id, "name": provider.name, "balance": provider.balance()} for provider in Provider.objects.all()]
        return Response([row for row in rows if row["balance"] < 0])

    @action(detail=False, methods=["get"], url_path="staff-by-event")
    def staff_by_event(self, request):
        event = get_object_or_404(Event, pk=request.query_params.get("event"))
        assignments = event.staff_assignments.select_related("employee", "role")
        return Response(EventStaffAssignmentSerializer(assignments, many=True).data)

    @action(detail=False, methods=["get"], url_path="taxes-paid")
    def taxes_paid(self, request):
        date_from, date_to = self._period(request)
        payments = TaxPayment.objects.filter(payment_date__gte=date_from, payment_date__lte=date_to).select_related("tax_type", "account")
        return Response(TaxPaymentSerializer(payments, many=True).data)

    @action(detail=False, methods=["get"], url_path="employee-payments")
    def employee_payments(self, request):
        date_from, date_to = self._period(request)
        payments = EmployeePayment.objects.filter(payment_date__gte=date_from, payment_date__lte=date_to).select_related(
            "employee",
            "event",
            "assignment",
            "cash_movement",
        )
        return Response(EmployeePaymentSerializer(payments, many=True).data)

    @action(detail=False, methods=["get"], url_path="taxes-due")
    def taxes_due(self, request):
        today = timezone.localdate()
        reminders = Reminder.objects.filter(
            status=Reminder.Status.PENDING,
            related_tax_payment__isnull=False,
            due_date__lte=today + timedelta(days=30),
        ).select_related("related_tax_payment__tax_type")
        return Response(ReminderSerializer(reminders, many=True).data)

    @action(detail=False, methods=["get"], url_path="voided-movements")
    def voided_movements(self, request):
        movements = CashMovement.objects.filter(status=CashMovement.Status.VOIDED).select_related("account", "code")
        return Response(CashMovementSerializer(movements, many=True).data)

    @action(detail=False, methods=["get"], url_path="transfers")
    def transfers(self, request):
        date_from, date_to = self._period(request)
        transfers = AccountTransfer.objects.filter(date__gte=date_from, date__lte=date_to).select_related("from_account", "to_account")
        return Response(AccountTransferSerializer(transfers, many=True).data)

    @action(detail=False, methods=["get"], url_path="event-summary")
    def event_summary(self, request):
        event = get_object_or_404(Event, pk=request.query_params.get("event"))
        movements = event.cash_movements.filter(status=CashMovement.Status.CONFIRMED)
        income = movements.filter(movement_type=CashMovement.MovementType.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        expense = movements.filter(movement_type=CashMovement.MovementType.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        return Response({"event": EventSerializer(event).data, "income": income, "expense": expense, "result": income - expense})
