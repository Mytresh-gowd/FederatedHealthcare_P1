from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospital", "0003_alter_submission_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="analytics_data",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
