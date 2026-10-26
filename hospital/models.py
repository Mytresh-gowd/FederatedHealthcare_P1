from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User

class Submission(models.Model):
    STATUS=[('TRAINED','Local model trained'),('SUBMITTED','Submitted to FL round'),('AGGREGATED','Included in global model')]

    hospital=models.ForeignKey(User,on_delete=models.CASCADE,related_name='submissions')
    filename=models.CharField(max_length=255)
    records=models.PositiveIntegerField(default=0)
    train_rows=models.PositiveIntegerField(default=0)
    validation_rows=models.PositiveIntegerField(default=0)
    test_rows=models.PositiveIntegerField(default=0)
    class_distribution=models.JSONField(default=dict,blank=True)
    analytics_data=models.JSONField(default=dict,blank=True)
    accuracy=models.FloatField(null=True,blank=True)
    macro_f1=models.FloatField(null=True,blank=True)
    trees=models.PositiveIntegerField(default=0)
    status=models.CharField(
        max_length=30,
        choices=STATUS,
        default='TRAINED'
    )
    round_no=models.PositiveIntegerField(default=1)
    model_version=models.CharField(
        max_length=50,
        default='v1.0.0'
    )
    artifact_path=models.CharField(
        max_length=500,
        blank=True
    )
    created_at=models.DateTimeField(auto_now_add=True)
    submitted_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering=['-created_at']

class FederatedRound(models.Model):
    STATUS=[('OPEN','Open'),('COMPLETED','Completed')]
    round_no=models.PositiveIntegerField(unique=True)
    clients=models.PositiveIntegerField(default=0)
    trees_per_client=models.PositiveIntegerField(default=60)
    global_trees=models.PositiveIntegerField(default=180)
    global_model_version=models.CharField(max_length=30,default='v1.0.0')
    status=models.CharField(max_length=20,choices=STATUS,default='OPEN')
    created_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)

class GlobalModel(models.Model):
    STATUS=[('AVAILABLE','Available'),('ACTIVE','Active')]
    version=models.CharField(max_length=30,unique=True)
    round_no=models.PositiveIntegerField(default=0)
    trees=models.PositiveIntegerField(default=180)
    accuracy=models.FloatField(null=True,blank=True)
    macro_f1=models.FloatField(null=True,blank=True)
    source_submissions=models.JSONField(default=list,blank=True)
    artifact_path=models.CharField(max_length=500)
    status=models.CharField(max_length=20,choices=STATUS,default='AVAILABLE')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-round_no', '-created_at']
        constraints = [
            models.UniqueConstraint(
                 fields=['status'],
                 condition=Q(status='ACTIVE'),
                 name='only_one_active_global_model'
            )
        ]
