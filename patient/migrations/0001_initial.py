from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[('auth','0012_alter_user_first_name_max_length')]
    operations=[migrations.CreateModel(name='Prediction',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('prediction',models.CharField(max_length=30)),('confidence',models.FloatField(blank=True,null=True)),
        ('probabilities',models.JSONField(blank=True,default=dict)),('input_snapshot',models.JSONField(blank=True,default=dict)),
        ('model_version',models.CharField(default='v1.0.0',max_length=50)),('created_at',models.DateTimeField(auto_now_add=True)),
        ('patient',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='predictions',to='auth.user')),
    ])]
