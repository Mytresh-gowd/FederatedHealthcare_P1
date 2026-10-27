from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("patient", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prediction",
            name="model_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
