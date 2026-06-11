from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Account,
    CashMovement,
    Employee,
    EmployeeRole,
    Event,
    EventStaffAssignment,
    MovementCode,
    Provider,
    ProviderLedgerEntry,
    Reminder,
    TaxType,
)
from .services import (
    calculate_account_balance,
    close_daily_account,
    close_daily_cash_group,
    create_account_transfer,
    create_balance_adjustment,
    register_employee_payment,
    register_provider_payment,
    register_tax_payment,
    void_cash_movement,
)


class CashflowServiceTests(TestCase):
    def setUp(self):
        call_command("seed_initial_data", verbosity=0)
        self.today = date(2026, 6, 10)
        self.cash = Account.objects.get(name="EFECTIVO")
        self.bank = Account.objects.get(name="BNA")
        self.provider = Provider.objects.first()
        self.employee = Employee.objects.first()
        self.role = EmployeeRole.objects.get(name="Mozo")
        self.event = Event.objects.first()
        self.tax_type = TaxType.objects.get(name="IVA")

    def code(self, code):
        return MovementCode.objects.get(code=code)

    def movement(self, movement_type, amount, code="OTRO_INGRESO", account=None, **kwargs):
        return CashMovement.objects.create(
            date_payment=self.today,
            description=f"Movimiento {code}",
            movement_type=movement_type,
            amount=Decimal(str(amount)),
            account=account or self.cash,
            code=self.code(code),
            status=CashMovement.Status.CONFIRMED,
            **kwargs,
        )

    def test_create_income_movement_updates_balance(self):
        self.movement(CashMovement.MovementType.INCOME, "100.00", "OTRO_INGRESO")
        self.assertEqual(calculate_account_balance(self.cash), Decimal("100.00"))

    def test_create_expense_movement_updates_balance(self):
        self.cash.initial_balance = Decimal("100.00")
        self.cash.save()
        self.movement(CashMovement.MovementType.EXPENSE, "35.50", "OTRO_EGRESO")
        self.assertEqual(calculate_account_balance(self.cash), Decimal("64.50"))

    def test_create_balance_adjustment_up_and_down(self):
        self.cash.initial_balance = Decimal("100.00")
        self.cash.save()
        up = create_balance_adjustment(self.cash, Decimal("130.00"), self.today)
        self.assertEqual(up.amount, Decimal("30.00"))
        self.assertEqual(up.movement_type, CashMovement.MovementType.ADJUSTMENT)
        self.assertEqual(calculate_account_balance(self.cash), Decimal("130.00"))

        down = create_balance_adjustment(self.cash, Decimal("80.00"), self.today)
        self.assertEqual(down.amount, Decimal("50.00"))
        self.assertEqual(down.movement_type, CashMovement.MovementType.EXPENSE)
        self.assertEqual(calculate_account_balance(self.cash), Decimal("80.00"))

    def test_void_movement_removes_it_from_balance(self):
        movement = self.movement(CashMovement.MovementType.INCOME, "100.00", "OTRO_INGRESO")
        void_cash_movement(movement, "Carga duplicada")
        self.assertEqual(calculate_account_balance(self.cash), Decimal("0.00"))
        movement.refresh_from_db()
        self.assertEqual(movement.status, CashMovement.Status.VOIDED)

    def test_account_transfer_creates_out_and_in_movements(self):
        self.cash.initial_balance = Decimal("100.00")
        self.cash.save()
        transfer = create_account_transfer(
            from_account=self.cash,
            to_account=self.bank,
            amount=Decimal("30.00"),
            fee_amount=Decimal("5.00"),
            transfer_date=self.today,
            description="Deposito",
        )
        self.assertEqual(transfer.cash_movements.count(), 3)
        self.assertEqual(calculate_account_balance(self.cash), Decimal("65.00"))
        self.assertEqual(calculate_account_balance(self.bank), Decimal("30.00"))

    def test_daily_account_close_calculates_totals(self):
        self.movement(CashMovement.MovementType.INCOME, "100.00", "OTRO_INGRESO")
        self.movement(CashMovement.MovementType.EXPENSE, "25.00", "OTRO_EGRESO")
        daily_close = close_daily_account(self.cash, self.today, Decimal("75.00"))
        self.assertEqual(daily_close.total_income, Decimal("100.00"))
        self.assertEqual(daily_close.total_expense, Decimal("25.00"))
        self.assertEqual(daily_close.calculated_balance, Decimal("75.00"))
        self.assertEqual(daily_close.difference, Decimal("0.00"))

    def test_daily_cash_group_closes_all_active_accounts(self):
        group = close_daily_cash_group(self.today, {str(self.cash.id): Decimal("0.00")})
        self.assertEqual(group.status, group.Status.CLOSED)
        self.assertEqual(group.account_closes.count(), Account.objects.filter(active=True).count())

    def test_provider_direct_payment_creates_cash_movement(self):
        entry = register_provider_payment(self.provider, self.cash, Decimal("150.00"), self.today, event=self.event)
        self.assertEqual(entry.entry_type, ProviderLedgerEntry.EntryType.PAYMENT)
        self.assertEqual(entry.cash_movement.amount, Decimal("150.00"))
        self.assertEqual(self.provider.balance(), Decimal("-150.00"))

    def test_provider_credit_balance_is_negative(self):
        register_provider_payment(self.provider, self.cash, Decimal("200.00"), self.today)
        self.assertLess(self.provider.balance(), Decimal("0.00"))

    def test_partial_employee_payment_updates_assignment(self):
        assignment = EventStaffAssignment.objects.create(
            event=self.event,
            employee=self.employee,
            role=self.role,
            work_date=self.today,
            base_amount=Decimal("100.00"),
        )
        register_employee_payment(self.employee, self.cash, Decimal("40.00"), self.today, assignment=assignment)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, EventStaffAssignment.Status.PARTIALLY_PAID)
        self.assertEqual(assignment.pending_amount(), Decimal("60.00"))

    def test_total_employee_payment_updates_assignment(self):
        assignment = EventStaffAssignment.objects.create(
            event=self.event,
            employee=self.employee,
            role=self.role,
            work_date=self.today,
            base_amount=Decimal("100.00"),
        )
        register_employee_payment(self.employee, self.cash, Decimal("100.00"), self.today, assignment=assignment)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, EventStaffAssignment.Status.PAID)
        self.assertEqual(assignment.pending_amount(), Decimal("0.00"))

    def test_tax_payment_with_reminder(self):
        tax_payment, reminder = register_tax_payment(
            self.tax_type,
            self.bank,
            Decimal("500.00"),
            self.today,
            period="2026-06",
            recurrence_type=Reminder.RecurrenceType.MONTHLY,
            remind_before_days=3,
        )
        self.assertIsNotNone(tax_payment.cash_movement)
        self.assertIsNotNone(reminder)
        self.assertEqual(reminder.due_date, date(2026, 7, 10))

    def test_cannot_create_movement_for_closed_account_day(self):
        close_daily_account(self.cash, self.today, Decimal("0.00"))
        with self.assertRaises(ValidationError):
            self.movement(CashMovement.MovementType.INCOME, "10.00", "OTRO_INGRESO")


class AuthenticationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="owner", password="secret123")

    def test_login_returns_token_and_me_endpoint_requires_auth(self):
        anonymous_response = self.client.get("/api/auth/me/")
        self.assertEqual(anonymous_response.status_code, 401)

        login_response = self.client.post("/api/auth/login/", {"username": "owner", "password": "secret123"}, format="json")
        self.assertEqual(login_response.status_code, 200)
        token = login_response.data["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["user"]["username"], "owner")
