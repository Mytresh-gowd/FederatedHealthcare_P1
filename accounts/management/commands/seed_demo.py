from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Profile
from hospital.models import FederatedRound, GlobalModel
from django.conf import settings

USERS=[('patient','patient123','PATIENT','Demo Patient',''),('hospital1','hospital123','HOSPITAL','Hospital 1','HOSPITAL-1'),('hospital2','hospital123','HOSPITAL','Hospital 2','HOSPITAL-2'),('hospital3','hospital123','HOSPITAL','Hospital 3','HOSPITAL-3'),('admin','admin123','ADMIN','System Admin','')]
class Command(BaseCommand):
    help='Create demo accounts and initial global model registry records.'
    def handle(self,*args,**kwargs):
        for username,password,role,name,client in USERS:
            u,created=User.objects.get_or_create(username=username,defaults={'first_name':name})
            if created: u.set_password(password)
            if role=='ADMIN': u.is_staff=True; u.is_superuser=True
            u.save()
            Profile.objects.update_or_create(user=u,defaults={'role':role,'organization':name if role=='HOSPITAL' else 'Federated Healthcare','client_id':client})
            r,_=FederatedRound.objects.get_or_create(
    round_no=1,
    defaults={
        'clients': 0,
        'trees_per_client': 60,
        'global_trees': 180,
        'status': 'OPEN',
        
    }
)
            base=Path(settings.BASE_DIR)/'ml_models'/'chronic_disease_rf.joblib'
        v1, created = GlobalModel.objects.update_or_create(
    version='v1.0.0',
    defaults={
        'round_no': 0,
        'trees': 180,
        'artifact_path': 'ml_models/chronic_disease_rf.joblib',
    }
)

# Only activate v1 if there is currently no active global model.
if not GlobalModel.objects.filter(status='ACTIVE').exists():
    GlobalModel.objects.filter(status='ACTIVE').update(status='AVAILABLE')
    v1.status = 'ACTIVE'
    v1.save(update_fields=['status'])