from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[('auth','0012_alter_user_first_name_max_length')]
    operations=[migrations.CreateModel(name='Profile',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('role',models.CharField(choices=[('PATIENT','Patient'),('HOSPITAL','Hospital'),('ADMIN','Admin')],default='PATIENT',max_length=20)),
        ('organization',models.CharField(blank=True,max_length=150)),
        ('client_id',models.CharField(blank=True,max_length=50)),
        ('user',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name='profile',to='auth.user')),
    ])]
