from django.db import models
from django.contrib.auth.models import User

class Prediction(models.Model):
    patient=models.ForeignKey(User,on_delete=models.CASCADE,related_name='predictions')
    prediction=models.CharField(max_length=30)
    confidence=models.FloatField(null=True,blank=True)
    probabilities=models.JSONField(default=dict,blank=True)
    input_snapshot=models.JSONField(default=dict,blank=True)
    model_version=models.CharField(max_length=50,default='v1.0.0')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
