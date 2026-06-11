from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
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
    EventStaffAssignmentViewSet,
    EventViewSet,
    MovementCodeViewSet,
    ProviderLedgerEntryViewSet,
    ProviderViewSet,
    ReminderViewSet,
    ReportsViewSet,
    TaxPaymentViewSet,
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
router.register("event-staff-assignments", EventStaffAssignmentViewSet)
router.register("employee-payments", EmployeePaymentViewSet)
router.register("tax-types", TaxTypeViewSet)
router.register("tax-payments", TaxPaymentViewSet)
router.register("reminders", ReminderViewSet)
router.register("reports", ReportsViewSet, basename="reports")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", LoginAPIView.as_view(), name="auth-login"),
    path("auth/me/", AuthStatusAPIView.as_view(), name="auth-me"),
    path("auth/logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("health/", HealthCheckAPIView.as_view(), name="health"),
    path("dashboard/", DashboardAPIView.as_view(), name="dashboard"),
]
