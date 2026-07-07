from decimal import Decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_event_payment_tokens(apps, schema_editor):
    Event = apps.get_model("cashflow", "Event")
    for event in Event.objects.filter(public_payment_token__isnull=True):
        token = uuid.uuid4()
        while Event.objects.filter(public_payment_token=token).exists():
            token = uuid.uuid4()
        event.public_payment_token = token
        event.save(update_fields=["public_payment_token"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cashflow", "0007_servicetype_employee_email_graduationevent_closed_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Presupuesto"),
                    ("SIGNALED", "Señado"),
                    ("CONFIRMED", "Confirmado"),
                    ("DONE", "Realizado"),
                    ("CLOSED", "Cerrado"),
                    ("CANCELLED", "Cancelado"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="public_payment_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(populate_event_payment_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="public_payment_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="closed_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_total_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_paid_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_pending_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_expense_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
        ),
        migrations.AddField(
            model_name="event",
            name="closed_result_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14),
        ),
    ]
