from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[('auth','0012_alter_user_first_name_max_length')]
    operations=[
        migrations.CreateModel(name='FederatedRound',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('round_no',models.PositiveIntegerField(unique=True)),('clients',models.PositiveIntegerField(default=0)),
            ('trees_per_client',models.PositiveIntegerField(default=60)),('global_trees',models.PositiveIntegerField(default=180)),
            ('status',models.CharField(choices=[('OPEN','Open'),('COMPLETED','Completed')],default='OPEN',max_length=20)),
            ('global_accuracy',models.FloatField(blank=True,null=True)),('global_macro_f1',models.FloatField(blank=True,null=True)),
            ('global_model_version',models.CharField(default='v1.0.0',max_length=50)),('created_at',models.DateTimeField(auto_now_add=True)),('completed_at',models.DateTimeField(blank=True,null=True)),
        ]),
        migrations.CreateModel(name='Submission',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('filename',models.CharField(max_length=255)),('records',models.PositiveIntegerField(default=0)),('accuracy',models.FloatField(blank=True,null=True)),('macro_f1',models.FloatField(blank=True,null=True)),('trees',models.PositiveIntegerField(default=0)),
            ('status',models.CharField(choices=[('READY','Ready'),('TRAINED','Local model trained'),('SUBMITTED','Submitted to FL round'),('AGGREGATED','Included in global model')],default='READY',max_length=30)),('round_no',models.PositiveIntegerField(default=0)),('model_version',models.CharField(default='v1.0.0',max_length=50)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('hospital',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='submissions',to='auth.user')),
        ])]
