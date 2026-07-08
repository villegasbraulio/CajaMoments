from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from cashflow.models import (
    Account,
    Client,
    Employee,
    EmployeeRole,
    Event,
    MovementCode,
    Provider,
    ServiceType,
    TaxType,
)


class Command(BaseCommand):
    help = "Carga datos iniciales de Caja Moments para Fase 1."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-examples",
            action="store_true",
            help="Carga solo datos maestros y omite proveedores, empleados, cliente y evento de ejemplo.",
        )

    def handle(self, *args, **options):
        self.seed_accounts()
        self.seed_movement_codes()
        self.seed_tax_types()
        self.seed_service_types()
        self.seed_employee_roles()
        if not options["skip_examples"]:
            self.seed_examples()
        self.stdout.write(self.style.SUCCESS("Datos iniciales cargados correctamente."))

    def seed_accounts(self):
        accounts = [
            ("EFECTIVO", Account.AccountType.CASH, Account.Currency.ARS),
            ("BNA", Account.AccountType.BANK, Account.Currency.ARS),
            ("MERCADO PAGO", Account.AccountType.WALLET, Account.Currency.ARS),
            ("NARANJA", Account.AccountType.WALLET, Account.Currency.ARS),
            ("PLAZO FIJO", Account.AccountType.INVESTMENT, Account.Currency.ARS),
            ("FRASCOS", Account.AccountType.INVESTMENT, Account.Currency.ARS),
            ("USD", Account.AccountType.FOREIGN_CURRENCY, Account.Currency.USD),
        ]
        for name, account_type, currency in accounts:
            Account.objects.get_or_create(
                name=name,
                defaults={
                    "type": account_type,
                    "currency": currency,
                    "initial_balance": Decimal("0.00"),
                },
            )

    def seed_movement_codes(self):
        codes = [
            ("COBRO_EVENTO", "Cobro de evento", MovementCode.MovementKind.INCOME, "Eventos", False, False, False, True),
            ("SEÑA_EVENTO", "Sena de evento", MovementCode.MovementKind.INCOME, "Eventos", False, False, False, True),
            ("PAGO_PROVEEDOR", "Pago a proveedor", MovementCode.MovementKind.EXPENSE, "Proveedores", True, False, False, False),
            ("PERSONAL_EVENTUAL", "Personal eventual", MovementCode.MovementKind.EXPENSE, "Personal", False, True, False, False),
            ("COCINA", "Cocina", MovementCode.MovementKind.EXPENSE, "Operativo", False, False, False, False),
            ("LIMPIEZA", "Limpieza", MovementCode.MovementKind.EXPENSE, "Operativo", False, False, False, False),
            ("CABINA", "Cabina", MovementCode.MovementKind.EXPENSE, "Operativo", False, False, False, False),
            ("IMPUESTOS", "Impuestos", MovementCode.MovementKind.EXPENSE, "Impuestos", False, False, True, False),
            ("SERVICIOS", "Servicios", MovementCode.MovementKind.EXPENSE, "Impuestos y servicios", False, False, False, False),
            ("TRANSFERENCIA_INTERNA", "Transferencia interna", MovementCode.MovementKind.TRANSFER, "Caja", False, False, False, False),
            ("INVERSION_PLAZO_FIJO", "Inversion plazo fijo", MovementCode.MovementKind.TRANSFER, "Inversiones", False, False, False, False),
            ("INVERSION_FRASCO", "Inversion frasco", MovementCode.MovementKind.TRANSFER, "Inversiones", False, False, False, False),
            ("RENDIMIENTO_INVERSION", "Rendimiento de inversion", MovementCode.MovementKind.INCOME, "Inversiones", False, False, False, False),
            ("AJUSTE_CAJA", "Ajuste de caja", MovementCode.MovementKind.ADJUSTMENT, "Caja", False, False, False, False),
            ("OTRO_INGRESO", "Otro ingreso", MovementCode.MovementKind.INCOME, "Otros", False, False, False, False),
            ("OTRO_EGRESO", "Otro egreso", MovementCode.MovementKind.EXPENSE, "Otros", False, False, False, False),
        ]
        for code, name, movement_type, category, requires_provider, requires_employee, requires_tax, requires_event in codes:
            MovementCode.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "movement_type": movement_type,
                    "category": category,
                    "requires_provider": requires_provider,
                    "requires_employee": requires_employee,
                    "requires_tax": requires_tax,
                    "requires_event": requires_event,
                    "active": True,
                },
            )

    def seed_tax_types(self):
        for name in ["Servicios", "Monotributo", "IVA", "Ingresos Brutos", "Autonomos", "Municipal"]:
            TaxType.objects.get_or_create(name=name)

    def seed_service_types(self):
        for name in ["Luz", "Agua", "Gas", "Internet", "Mantenimiento", "Otro"]:
            ServiceType.objects.get_or_create(name=name)

    def seed_employee_roles(self):
        for name in ["Mozo", "Cocina", "Cabina", "Limpieza anterior", "Limpieza posterior", "Armado", "Produccion", "Barra", "Otro"]:
            EmployeeRole.objects.get_or_create(name=name)

    def seed_examples(self):
        Provider.objects.get_or_create(name="Proveedor ejemplo catering", defaults={"category": "Catering", "phone": "2610000000"})
        Provider.objects.get_or_create(name="Proveedor ejemplo sonido", defaults={"category": "Tecnica", "phone": "2611111111"})

        Employee.objects.get_or_create(first_name="Ana", last_name="Gomez", document_number="10000001", defaults={"alias": "Ani"})
        Employee.objects.get_or_create(first_name="Luis", last_name="Perez", document_number="10000002", defaults={"alias": "Lucho"})

        client, _ = Client.objects.get_or_create(name="Cliente ejemplo", defaults={"phone": "2612222222"})
        Event.objects.get_or_create(
            name="Evento ejemplo",
            defaults={
                "client": client,
                "event_type": Event.Type.QUINCE,
                "event_date": timezone.localdate(),
                "status": Event.Status.CONFIRMED,
            },
        )
