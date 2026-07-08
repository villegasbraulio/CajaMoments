from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cashflow", "0011_parametrize_event_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventbudgetpayment",
            name="payment_purpose",
            field=models.CharField(
                choices=[
                    ("DEPOSIT", "Seña"),
                    ("ADVANCE", "Adelanto"),
                    ("BUDGET_ITEM", "Servicio"),
                ],
                default="ADVANCE",
                max_length=20,
            ),
        ),
        migrations.RunSQL(
            "UPDATE cashflow_eventbudgetpayment SET payment_purpose = 'BUDGET_ITEM' WHERE budget_item_id IS NOT NULL",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            """
            UPDATE cashflow_eventbudgetpayment
            SET payment_purpose = 'DEPOSIT'
            WHERE budget_item_id IS NULL
              AND cash_movement_id IN (
                SELECT cm.id
                FROM cashflow_cashmovement cm
                JOIN cashflow_movementcode mc ON cm.code_id = mc.id
                WHERE mc.code = 'SEÑA_EVENTO'
              )
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
