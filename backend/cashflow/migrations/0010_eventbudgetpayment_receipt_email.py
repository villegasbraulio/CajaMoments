from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cashflow", "0009_graduationticketprice_valid_until"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventbudgetpayment",
            name="receipt_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
