from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditLogEntryViewSet,
    AccountTransferViewSet,
    AccountViewSet,
    AuthStatusAPIView,
    CashMovementViewSet,
    ClientViewSet,
    DailyAccountCloseViewSet,
    DailyCashCloseGroupViewSet,
    DashboardAPIView,
    HealthCheckAPIView,
    LoginAPIView,
    LogoutAPIView,
    EmployeePaymentViewSet,
    EmployeeRoleViewSet,
    EmployeeViewSet,
    EventBudgetItemViewSet,
    EventBudgetPaymentPreferenceAPIView,
    EventBudgetPaymentViewSet,
    EventBudgetPaymentWebhookAPIView,
    EventBudgetViewSet,
    EventStaffAssignmentViewSet,
    EventViewSet,
    GraduateViewSet,
    GraduationEventGraduateSearchAPIView,
    GraduationEventPublicAPIView,
    GraduationEventViewSet,
    GraduationTicketPriceViewSet,
    MovementCodeViewSet,
    ProviderLedgerEntryViewSet,
    ProviderViewSet,
    ReminderViewSet,
    ReportsViewSet,
    TaxPaymentViewSet,
    ServicePaymentAPIView,
    ServiceTypeViewSet,
    TicketPurchaseManualAPIView,
    TicketPurchasePreferenceAPIView,
    TicketPurchaseViewSet,
    TicketPurchaseWebhookAPIView,
    TaxTypeViewSet,
)


router = DefaultRouter()
router.register("accounts", AccountViewSet)
router.register("movement-codes", MovementCodeViewSet)
router.register("cash-movements", CashMovementViewSet)
router.register("account-transfers", AccountTransferViewSet)
router.register("daily-cash-closes", DailyCashCloseGroupViewSet)
router.register("daily-account-closes", DailyAccountCloseViewSet)
router.register("providers", ProviderViewSet)
router.register("provider-ledger", ProviderLedgerEntryViewSet)
router.register("employees", EmployeeViewSet)
router.register("employee-roles", EmployeeRoleViewSet)
router.register("clients", ClientViewSet)
router.register("events", EventViewSet)
router.register("event-budgets", EventBudgetViewSet)
router.register("event-budget-items", EventBudgetItemViewSet)
router.register("event-budget-payments", EventBudgetPaymentViewSet)
router.register("event-staff-assignments", EventStaffAssignmentViewSet)
router.register("employee-payments", EmployeePaymentViewSet)
router.register("graduation-events", GraduationEventViewSet)
router.register("graduation-ticket-prices", GraduationTicketPriceViewSet)
router.register("graduates", GraduateViewSet)
router.register("ticket-purchases", TicketPurchaseViewSet)
router.register("service-types", ServiceTypeViewSet)
router.register("tax-types", TaxTypeViewSet)
router.register("tax-payments", TaxPaymentViewSet)
router.register("reminders", ReminderViewSet)
router.register("audit-log", AuditLogEntryViewSet)
router.register("reports", ReportsViewSet, basename="reports")

urlpatterns = [
    path("auth/login/", LoginAPIView.as_view(), name="auth-login"),
    path("auth/me/", AuthStatusAPIView.as_view(), name="auth-me"),
    path("auth/logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("health/", HealthCheckAPIView.as_view(), name="health"),
    path("dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("event-budget-payments/create-preference/", EventBudgetPaymentPreferenceAPIView.as_view(), name="event-budget-payment-preference"),
    path("event-budget-payments/webhook/", EventBudgetPaymentWebhookAPIView.as_view(), name="event-budget-payment-webhook"),
    path("graduation-events/<uuid:token>/public/", GraduationEventPublicAPIView.as_view(), name="graduation-event-public"),
    path("graduation-events/<uuid:token>/graduates/search/", GraduationEventGraduateSearchAPIView.as_view(), name="graduation-event-graduate-search"),
    path("ticket-purchases/create-preference/", TicketPurchasePreferenceAPIView.as_view(), name="ticket-purchase-preference"),
    path("ticket-purchases/manual/", TicketPurchaseManualAPIView.as_view(), name="ticket-purchase-manual"),
    path("ticket-purchases/webhook/", TicketPurchaseWebhookAPIView.as_view(), name="ticket-purchase-webhook"),
    path("service-payments/", ServicePaymentAPIView.as_view(), name="service-payment"),
    path("", include(router.urls)),
]
