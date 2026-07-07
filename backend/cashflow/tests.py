from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import (
    Account,
    CashMovement,
    Client,
    Employee,
    EmployeeRole,
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
    TicketPurchase,
    TaxType,
    AuditLogEntry,
)
from .services import (
    calculate_account_balance,
    close_daily_account,
    close_daily_cash_group,
    create_account_transfer,
    create_balance_adjustment,
    create_event_budget_payment_preference,
    build_cash_movement_receipt_pdf,
    create_ticket_purchase_preference,
    close_graduation_event,
    export_daily_account_close_csv,
    get_event_overview,
    register_event_budget_item_manual_payment,
    register_employee_payment,
    register_provider_payment,
    register_service_payment,
    register_ticket_purchase_manual,
    register_tax_payment,
    sync_event_budget_payment,
    sync_ticket_purchase_payment,
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

    def test_daily_close_export_includes_transfer_movements(self):
        transfer = create_account_transfer(
            from_account=self.cash,
            to_account=self.bank,
            amount=Decimal("30.00"),
            transfer_date=self.today,
            description="Deposito",
        )
        daily_close = close_daily_account(self.cash, self.today, Decimal("-30.00"))
        self.assertEqual(daily_close.total_transfer_out, Decimal("30.00"))
        content = export_daily_account_close_csv(daily_close)
        self.assertIn("TRANSFER_OUT", content)
        self.assertIn("TRANSFERENCIA_INTERNA", content)
        self.assertIn(str(transfer.id), str(CashMovement.objects.filter(transfer=transfer).first().transfer_id))

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

    def test_non_staff_user_cannot_mutate_operational_resources(self):
        login_response = self.client.post("/api/auth/login/", {"username": "owner", "password": "secret123"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login_response.data['token']}")
        response = self.client.post(
            "/api/accounts/",
            {"name": "Cuenta prueba", "type": "CASH", "currency": "ARS", "initial_balance": "0.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class EventModuleStageOneTests(TestCase):
    def setUp(self):
        call_command("seed_initial_data", verbosity=0)
        self.client_api = APIClient()
        self.user = get_user_model().objects.create_user(username="planner", password="secret123", is_staff=True)
        login_response = self.client_api.post("/api/auth/login/", {"username": "planner", "password": "secret123"}, format="json")
        self.client_api.credentials(HTTP_AUTHORIZATION=f"Token {login_response.data['token']}")
        self.client_obj = Client.objects.get(name="Cliente ejemplo")
        self.event = Event.objects.get(name="Evento ejemplo")
        self.cash = Account.objects.get(name="EFECTIVO")
        self.provider = Provider.objects.first()
        self.employee = Employee.objects.first()
        self.role = EmployeeRole.objects.get(name="Mozo")

    def test_can_create_event_with_extended_stage_one_fields(self):
        response = self.client_api.post(
            "/api/events/",
            {
                "client": self.client_obj.id,
                "name": "Casamiento Abril",
                "event_type": "Casamiento",
                "event_date": "2026-07-20",
                "event_time": "21:30:00",
                "venue_space": "Salon principal",
                "guest_count_dinner": 180,
                "guest_count_toast": 220,
                "main_table_notes": "Mesa principal para 12 personas",
                "tableware_notes": "Manteleria blanca y dorada",
                "protocol_notes": "Entrada con recepcion de fotos",
                "beverage_notes": "Barra libre despues del brindis",
                "additional_notes": "Cabina 360 y livings exteriores",
                "operational_notes": "Verificar montaje el dia anterior",
                "internal_status": "Listo para presupuestar",
                "contact_name": "Lucia Perez",
                "contact_phone": "2615551234",
                "contact_email": "lucia@example.com",
                "status": Event.Status.CONFIRMED,
                "notes": "Evento de alto volumen",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["venue_space"], "Salon principal")
        self.assertEqual(response.data["guest_count_total"], 220)
        self.assertEqual(response.data["client_name"], self.client_obj.name)

    def test_event_overview_returns_operational_and_financial_summary(self):
        EventStaffAssignment.objects.create(
            event=self.event,
            employee=self.employee,
            role=self.role,
            work_date=date(2026, 6, 20),
            base_amount=Decimal("120.00"),
        )
        register_provider_payment(self.provider, self.cash, Decimal("80.00"), date(2026, 6, 20), event=self.event)
        overview = get_event_overview(self.event)
        self.assertEqual(overview["linked_counts"]["assignments"], 1)
        self.assertEqual(overview["financial"]["expense"], Decimal("80.00"))
        self.assertEqual(overview["financial"]["staffing_cost"], Decimal("120.00"))

        response = self.client_api.get(f"/api/events/{self.event.id}/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["linked_counts"]["assignments"], 1)
        self.assertIn("service_snapshot", response.data)


class EventBudgetStageTwoTests(TestCase):
    def setUp(self):
        call_command("seed_initial_data", verbosity=0)
        self.client_api = APIClient()
        self.user = get_user_model().objects.create_user(username="budgeter", password="secret123", is_staff=True)
        login_response = self.client_api.post("/api/auth/login/", {"username": "budgeter", "password": "secret123"}, format="json")
        self.client_api.credentials(HTTP_AUTHORIZATION=f"Token {login_response.data['token']}")
        self.event = Event.objects.get(name="Evento ejemplo")

    def test_budget_endpoint_creates_budget_if_missing(self):
        self.assertFalse(hasattr(self.event, "budget"))
        response = self.client_api.get(f"/api/events/{self.event.id}/budget/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["event"], self.event.id)
        self.assertEqual(response.data["item_count"], 0)
        self.assertTrue(EventBudget.objects.filter(event=self.event).exists())

    def test_budget_item_calculates_total_and_event_overview_exposes_summary(self):
        budget = EventBudget.objects.create(event=self.event)
        response = self.client_api.post(
            "/api/event-budget-items/",
            {
                "budget": budget.id,
                "service_name": "Personas a la cena",
                "category": "Servicio",
                "quantity": "100.00",
                "unit_label": "personas",
                "unit_price": "700.00",
                "sort_order": 1,
                "is_optional": False,
                "notes": "Menu principal",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "70000.00")

        EventBudgetItem.objects.create(
            budget=budget,
            service_name="Cabina 360",
            category="Opcional",
            quantity=Decimal("1.00"),
            unit_price=Decimal("8500.00"),
            is_optional=True,
            sort_order=2,
        )

        budget_response = self.client_api.get(f"/api/events/{self.event.id}/budget/")
        self.assertEqual(budget_response.status_code, 200)
        self.assertEqual(Decimal(str(budget_response.data["subtotal"])), Decimal("70000.00"))
        self.assertEqual(Decimal(str(budget_response.data["optional_total"])), Decimal("8500.00"))
        self.assertEqual(Decimal(str(budget_response.data["grand_total"])), Decimal("78500.00"))

        overview_response = self.client_api.get(f"/api/events/{self.event.id}/overview/")
        self.assertEqual(overview_response.status_code, 200)
        self.assertEqual(Decimal(str(overview_response.data["budget_summary"]["grand_total"])), Decimal("78500.00"))


class EventBudgetPaymentStageThreeTests(TestCase):
    def setUp(self):
        call_command("seed_initial_data", verbosity=0)
        self.client_api = APIClient()
        self.user = get_user_model().objects.create_user(username="collector", password="secret123", is_staff=True)
        login_response = self.client_api.post("/api/auth/login/", {"username": "collector", "password": "secret123"}, format="json")
        self.client_api.credentials(HTTP_AUTHORIZATION=f"Token {login_response.data['token']}")
        self.event = Event.objects.get(name="Evento ejemplo")
        self.budget = EventBudget.objects.create(event=self.event)
        EventBudgetItem.objects.create(
            budget=self.budget,
            service_name="Servicio integral",
            quantity=Decimal("2.00"),
            unit_price=Decimal("1000.00"),
        )

    @patch("cashflow.services.MercadoPagoClient")
    def test_create_preference_records_payment_attempt(self, mercado_pago_client):
        mercado_pago_client.return_value.create_budget_preference.return_value = {
            "id": "pref_123",
            "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_123",
            "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_123",
        }
        payment = create_event_budget_payment_preference(self.budget)
        self.assertEqual(payment.amount, Decimal("2000.00"))
        self.assertEqual(payment.mp_preference_id, "pref_123")

        response = self.client_api.post("/api/event-budget-payments/create-preference/", {"budget": self.budget.id}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["preference_id"], "pref_123")
        self.assertEqual(EventBudgetPayment.objects.count(), 1)

    @patch("cashflow.services.MercadoPagoClient")
    def test_budget_item_manual_and_mp_payments_create_cash_movement(self, mercado_pago_client):
        item = self.budget.items.get(service_name="Servicio integral")
        manual = register_event_budget_item_manual_payment(item, Account.objects.get(name="EFECTIVO"), payment_date=date(2026, 6, 12))
        self.assertEqual(manual.budget_item, item)
        self.assertEqual(manual.cash_movement.amount, Decimal("2000.00"))
        self.assertEqual(manual.cash_movement.code.code, "COBRO_EVENTO")

        mercado_pago_client.return_value.create_budget_preference.return_value = {
            "id": "pref_item",
            "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_item",
            "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_item",
        }
        response = self.client_api.post(
            "/api/event-budget-payments/create-preference/",
            {"budget": self.budget.id, "budget_item": item.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["budget_item"], item.id)

    def test_cash_movement_receipt_endpoint_returns_pdf(self):
        movement = CashMovement.objects.create(
            date_payment=date(2026, 6, 12),
            description="Cobro evento",
            movement_type=CashMovement.MovementType.INCOME,
            amount=Decimal("500.00"),
            account=Account.objects.get(name="EFECTIVO"),
            code=MovementCode.objects.get(code="COBRO_EVENTO"),
            event=self.event,
            status=CashMovement.Status.CONFIRMED,
        )
        self.assertTrue(build_cash_movement_receipt_pdf(movement).startswith(b"%PDF"))
        response = self.client_api.get(f"/api/cash-movements/{movement.id}/receipt/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_sync_approved_payment_approves_budget(self):
        payment = EventBudgetPayment.objects.create(
            budget=self.budget,
            amount=Decimal("2000.00"),
            currency="ARS",
            mp_preference_id="pref_123",
        )
        payload = {
            "id": "pay_123",
            "status": "approved",
            "external_reference": f"event-budget-payment:{payment.id}",
            "transaction_amount": "2000.00",
            "currency_id": "ARS",
            "payment_method_id": "visa",
            "payment_type_id": "credit_card",
            "installments": 1,
            "date_approved": "2026-06-12T10:20:30.000-03:00",
        }
        sync_event_budget_payment(payment.id, payload)
        sync_event_budget_payment(payment.id, payload)
        payment.refresh_from_db()
        self.budget.refresh_from_db()
        self.assertEqual(payment.status, EventBudgetPayment.Status.APPROVED)
        self.assertEqual(self.budget.status, EventBudget.Status.APPROVED)
        self.assertIsNotNone(payment.cash_movement)
        self.assertEqual(payment.cash_movement.amount, Decimal("2000.00"))
        self.assertEqual(payment.cash_movement.date_payment, date(2026, 6, 12))
        self.assertEqual(payment.cash_movement.account.name, "MERCADO PAGO")
        self.assertEqual(payment.cash_movement.code.code, "COBRO_EVENTO")
        self.assertEqual(
            CashMovement.objects.filter(event=self.event, code__code="COBRO_EVENTO", amount=Decimal("2000.00")).count(),
            1,
        )

    def test_refunded_payment_creates_one_reversal_movement(self):
        payment = EventBudgetPayment.objects.create(
            budget=self.budget,
            amount=Decimal("2000.00"),
            currency="ARS",
            mp_preference_id="pref_123",
        )
        approved_payload = {
            "id": "pay_123",
            "status": "approved",
            "external_reference": f"event-budget-payment:{payment.id}",
            "transaction_amount": "2000.00",
            "currency_id": "ARS",
            "date_approved": "2026-06-12T10:20:30.000-03:00",
        }
        refund_payload = {
            "id": "pay_123",
            "status": "refunded",
            "date_approved": "2026-06-13T09:00:00.000-03:00",
        }
        sync_event_budget_payment(payment.id, approved_payload)
        sync_event_budget_payment(payment.id, refund_payload)
        sync_event_budget_payment(payment.id, refund_payload)

        payment.refresh_from_db()
        reversal = CashMovement.objects.get(voucher_number="pay_123-reversal")
        self.assertEqual(payment.status, EventBudgetPayment.Status.REFUNDED)
        self.assertEqual(reversal.movement_type, CashMovement.MovementType.EXPENSE)
        self.assertEqual(reversal.amount, Decimal("2000.00"))
        self.assertEqual(reversal.date_payment, date(2026, 6, 13))
        self.assertEqual(CashMovement.objects.filter(voucher_number="pay_123-reversal").count(), 1)

    @override_settings(MERCADOPAGO_WEBHOOK_SIGNATURE_REQUIRED=True, MERCADOPAGO_WEBHOOK_SECRET="secret")
    def test_webhook_rejects_invalid_signature(self):
        response = self.client_api.post(
            "/api/event-budget-payments/webhook/?type=payment&data.id=pay_123",
            {"type": "payment", "data": {"id": "pay_123"}},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class GraduationTicketTests(TestCase):
    def setUp(self):
        call_command("seed_initial_data", verbosity=0)
        self.client_api = APIClient()
        self.event = Event.objects.get(name="Evento ejemplo")
        self.graduation_event = GraduationEvent.objects.create(event=self.event, price_per_ticket=Decimal("1500.00"), capacity=100, max_tickets_per_graduate=3)
        GraduationTicketPrice.objects.create(graduation_event=self.graduation_event, price=Decimal("1500.00"), valid_from=date(2026, 6, 1))
        self.graduate = Graduate.objects.create(graduation_event=self.graduation_event, first_name="Ana", last_name="Lopez")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    @patch("cashflow.services.MercadoPagoClient")
    def test_public_ticket_purchase_summary_checkout_and_payment_sync(self, mercado_pago_client):
        mercado_pago_client.return_value.create_ticket_preference.return_value = {
            "id": "pref_ticket",
            "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_ticket",
            "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref_ticket",
        }
        public_response = self.client_api.get(f"/api/graduation-events/{self.graduation_event.public_token}/public/")
        self.assertEqual(public_response.status_code, 200)
        search_response = self.client_api.get(f"/api/graduation-events/{self.graduation_event.public_token}/graduates/search/?search=ana")
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.data[0]["display_name"], "Ana Lopez")

        purchase = create_ticket_purchase_preference(self.graduation_event, self.graduate, 2, "ana@example.com")
        self.assertEqual(purchase.total_amount, Decimal("3000.00"))
        self.assertEqual(purchase.mp_preference_id, "pref_ticket")
        self.assertEqual(len(mail.outbox), 1)

        approved_payload = {
            "id": "ticket_pay_123",
            "status": "approved",
            "external_reference": f"ticket-purchase:{purchase.id}",
            "transaction_amount": "3000.00",
            "currency_id": "ARS",
            "date_approved": "2026-06-12T10:20:30.000-03:00",
        }
        sync_ticket_purchase_payment(purchase.id, approved_payload)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, TicketPurchase.Status.PAID)
        self.assertIsNotNone(purchase.cash_movement)
        self.assertEqual(purchase.cash_movement.amount, Decimal("3000.00"))

        refund_payload = {"id": "ticket_pay_123", "status": "refunded", "date_approved": "2026-06-13T09:00:00.000-03:00"}
        sync_ticket_purchase_payment(purchase.id, refund_payload)
        sync_ticket_purchase_payment(purchase.id, refund_payload)
        self.assertEqual(CashMovement.objects.filter(voucher_number="ticket_pay_123-ticket-reversal").count(), 1)

    def test_ticket_price_limit_manual_payment_close_and_audit(self):
        user = get_user_model().objects.create_user(username="ticket-admin", password="secret123", is_staff=True)
        cash = Account.objects.get(name="EFECTIVO")
        GraduationTicketPrice.objects.create(graduation_event=self.graduation_event, price=Decimal("2000.00"), valid_from=date(2026, 7, 1))
        self.assertEqual(self.graduation_event.current_ticket_price(date(2026, 7, 10)), Decimal("2000.00"))

        purchase = register_ticket_purchase_manual(
            self.graduation_event,
            self.graduate,
            2,
            cash,
            email="ana@example.com",
            payment_date=date(2026, 7, 10),
            payment_method="Efectivo",
            user=user,
        )
        self.assertEqual(purchase.total_amount, Decimal("4000.00"))
        self.assertEqual(purchase.cash_movement.amount, Decimal("4000.00"))
        self.assertEqual(purchase.created_by, user)
        self.assertTrue(AuditLogEntry.objects.filter(user=user, action="ticket_purchase_manual").exists())

        with self.assertRaises(ValidationError):
            register_ticket_purchase_manual(self.graduation_event, self.graduate, 2, cash)

        close_graduation_event(self.graduation_event, user=user)
        self.graduation_event.refresh_from_db()
        self.assertIsNotNone(self.graduation_event.closed_at)
        with self.assertRaises(ValidationError):
            register_ticket_purchase_manual(self.graduation_event, self.graduate, 1, cash)


class PaymentsAndAuditTests(TestCase):
    def setUp(self):
        call_command("seed_initial_data", verbosity=0)
        self.user = get_user_model().objects.create_user(username="ops", password="secret123", is_staff=True)
        self.cash = Account.objects.get(name="EFECTIVO")

    def test_employee_email_and_service_payment_audit(self):
        employee = Employee.objects.create(first_name="Eva", last_name="Diaz", document_number="200", email="eva@example.com")
        self.assertEqual(employee.email, "eva@example.com")
        service_type, _ = ServiceType.objects.get_or_create(name="Internet")
        movement = register_service_payment(service_type, self.cash, Decimal("123.00"), date(2026, 7, 10), "Fibra", "Transferencia", self.user)
        self.assertEqual(movement.service_type, service_type)
        self.assertEqual(movement.code.code, "SERVICIOS")
        self.assertTrue(AuditLogEntry.objects.filter(user=self.user, action="service_payment", object_id=str(movement.id)).exists())
