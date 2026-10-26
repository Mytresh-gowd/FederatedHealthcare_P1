from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('hospital','0001_initial')]
    operations=[
        migrations.AddField(model_name='submission',name='train_rows',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='submission',name='validation_rows',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='submission',name='test_rows',field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='submission',name='class_distribution',field=models.JSONField(blank=True,default=dict)),
        migrations.AddField(model_name='submission',name='artifact_path',field=models.CharField(blank=True,max_length=500)),
        migrations.AddField(model_name='submission',name='submitted_at',field=models.DateTimeField(blank=True,null=True)),
        migrations.AlterField(model_name='submission',name='status',field=models.CharField(choices=[('TRAINED','Local model trained'),('SUBMITTED','Submitted to FL round'),('AGGREGATED','Included in global model')],default='TRAINED',max_length=30)),
        migrations.CreateModel(name='GlobalModel',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('version',models.CharField(max_length=30,unique=True)),('round_no',models.PositiveIntegerField(default=0)),('trees',models.PositiveIntegerField(default=180)),('accuracy',models.FloatField(blank=True,null=True)),('macro_f1',models.FloatField(blank=True,null=True)),('source_submissions',models.JSONField(blank=True,default=list)),('artifact_path',models.CharField(max_length=500)),('status',models.CharField(choices=[('AVAILABLE','Available'),('ACTIVE','Active')],default='AVAILABLE',max_length=20)),('created_at',models.DateTimeField(auto_now_add=True))],options={'ordering':['-round_no','-created_at']})
    ]
