from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('hospital', '0004_submission_analytics_data')]
    operations = [
        migrations.CreateModel(
            name='SupersetModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('version', models.CharField(max_length=30, unique=True)),
                ('source_versions', models.JSONField(blank=True, default=list)),
                ('trees', models.PositiveIntegerField(default=0)),
                ('artifact_path', models.CharField(max_length=500)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
