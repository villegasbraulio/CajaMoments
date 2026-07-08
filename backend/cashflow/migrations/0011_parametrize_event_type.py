from django.db import migrations, models


def normalize_event_types(apps, schema_editor):
    Event = apps.get_model("cashflow", "Event")
    mapping = {
        "": "EVENTO_PRIVADO",
        "boda": "CASAMIENTO",
        "casamiento": "CASAMIENTO",
        "cumple": "QUINCE",
        "cumpleanos": "QUINCE",
        "cumpleaños": "QUINCE",
        "cumpleanos de 15": "QUINCE",
        "cumpleaños de 15": "QUINCE",
        "egresados": "EGRESADOS",
        "social": "EVENTO_PRIVADO",
        "corporativo": "EVENTO_PRIVADO",
        "evento privado": "EVENTO_PRIVADO",
    }
    for event in Event.objects.all().only("id", "event_type"):
        normalized = mapping.get((event.event_type or "").strip().lower(), "EVENTO_PRIVADO")
        if event.event_type != normalized:
            Event.objects.filter(pk=event.pk).update(event_type=normalized)


class Migration(migrations.Migration):

    dependencies = [
        ("cashflow", "0010_eventbudgetpayment_receipt_email"),
    ]

    operations = [
        migrations.RunPython(normalize_event_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("QUINCE", "Cumpleaños de 15"),
                    ("EGRESADOS", "Egresados"),
                    ("EVENTO_PRIVADO", "Evento privado"),
                    ("CASAMIENTO", "Casamiento"),
                ],
                default="EVENTO_PRIVADO",
                max_length=32,
            ),
        ),
    ]
