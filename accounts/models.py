from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES=[('PATIENT','Patient'),('HOSPITAL','Hospital'),('ADMIN','Admin')]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile')
    role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='PATIENT')
    organization=models.CharField(max_length=150,blank=True)
    client_id=models.CharField(max_length=50,blank=True)
    def __str__(self): return f'{self.user.username} ({self.role})'
