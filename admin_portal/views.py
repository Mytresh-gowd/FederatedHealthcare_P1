from pathlib import Path
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from django.utils import timezone
from patient.models import Prediction
from hospital.models import Submission,FederatedRound,GlobalModel
from services.ml_service import model_info
from services.fl_service import aggregate,UPLOAD_DIR,LOCAL_TREES,EXPECTED_CLIENTS

def staff(u): return u.is_authenticated and (u.is_staff or getattr(getattr(u,'profile',None),'role',None)=='ADMIN')
def guard(view): return user_passes_test(staff,login_url='/login/')(view)

@guard
def dashboard(request):
    latest=GlobalModel.objects.first(); active=GlobalModel.objects.filter(status='ACTIVE').first(); open_round=FederatedRound.objects.filter(status='OPEN').order_by('-round_no').first()
    pending=Submission.objects.filter(status='SUBMITTED').select_related('hospital__profile').order_by('-submitted_at','-created_at')
    return render(request,'admin_portal/dashboard.html',{'latest':latest,'active':active,'open_round':open_round,'pending':pending,'patients':User.objects.filter(profile__role='PATIENT').count(),'predictions':Prediction.objects.count(),'hospital_count':User.objects.filter(profile__role='HOSPITAL').count(),'model':model_info(),'expected_clients':EXPECTED_CLIENTS})

@guard
def hospitals(request):
    return render(request,'admin_portal/hospitals.html',{'items':Submission.objects.select_related('hospital__profile').order_by('-created_at')})

@guard
def patients(request):
    return render(request,'admin_portal/patients.html',{'items':Prediction.objects.select_related('patient').order_by('-created_at')})

@guard
def rounds(request):
    items=FederatedRound.objects.all().order_by('-round_no'); pending={}
    for r in items:
        qs=Submission.objects.filter(round_no=r.round_no,status='SUBMITTED').select_related('hospital__profile')
        unique={}
        for s in qs: unique.setdefault(s.hospital_id,s)
        pending[r.round_no]=list(unique.values())
    return render(request,'admin_portal/rounds.html',{'items':items,'pending':pending,'expected_clients':EXPECTED_CLIENTS,'local_trees':LOCAL_TREES,'model':model_info()})

@guard
@require_POST
def aggregate_round(request,round_no):
    rnd=get_object_or_404(FederatedRound,round_no=round_no)
    if rnd.status!='OPEN': messages.info(request,'This round is already completed.'); return redirect('admin_rounds')
    selected_ids=[int(x) for x in request.POST.getlist('submission_ids') if x.isdigit()]
    subs=list(Submission.objects.filter(id__in=selected_ids,round_no=round_no,status='SUBMITTED').select_related('hospital__profile'))
    unique={}
    for s in subs: unique.setdefault(s.hospital_id,s)
    subs=list(unique.values())
    hospital_ids={s.hospital.profile.client_id or s.hospital.username for s in subs}
    if len(subs)!=EXPECTED_CLIENTS or len(hospital_ids)!=EXPECTED_CLIENTS:
        messages.error(request,f'Select exactly one submitted update from each of Hospital 1, Hospital 2 and Hospital 3. Selected: {len(subs)}.')
        return redirect('admin_rounds')
    bundle=[]
    for s in subs:
        cid=s.hospital.profile.client_id or s.hospital.username; path=UPLOAD_DIR/f'{cid}_round_{round_no}.joblib'
        if not path.exists(): messages.error(request,f'Model artifact for {s.hospital.profile.organization} is missing. Retrain that hospital.'); return redirect('admin_rounds')
        bundle.append({'path':str(path)})
    try:
        out,trees=aggregate(round_no,bundle)
        acc=sum((s.accuracy or 0) for s in subs)/len(subs); f1=sum((s.macro_f1 or 0) for s in subs)/len(subs)
        version=f'v{round_no+1}.0.0'
        GlobalModel.objects.filter(status='ACTIVE').update(status='AVAILABLE')
        gm=GlobalModel.objects.create(version=version,round_no=round_no,trees=trees,accuracy=acc,macro_f1=f1,source_submissions=[s.id for s in subs],artifact_path=str(Path(out).relative_to(Path(__file__).resolve().parents[1])),status='ACTIVE')
        # Normalize artifact path to project-relative path.
        gm.artifact_path=str(Path(out).relative_to(Path(__file__).resolve().parents[1])); gm.save(update_fields=['artifact_path'])
        Submission.objects.filter(id__in=[s.id for s in subs]).update(status='AGGREGATED')
        rnd.clients=len(subs); rnd.trees_per_client=LOCAL_TREES; rnd.global_trees=trees; rnd.status='COMPLETED'; rnd.completed_at=timezone.now(); rnd.save()
        FederatedRound.objects.get_or_create(round_no=round_no+1,defaults={'clients':0,'trees_per_client':LOCAL_TREES,'global_trees':EXPECTED_CLIENTS*LOCAL_TREES,'status':'OPEN'})
        messages.success(request,f'{version} created from one update each from Hospital 1, Hospital 2 and Hospital 3. It is now the active patient model.')
    except Exception as exc: messages.error(request,f'Aggregation failed: {exc}')
    return redirect('admin_dashboard')

@guard
def model_history(request):
 models=[]
 for m in GlobalModel.objects.all():
  sources=list(Submission.objects.filter(id__in=m.source_submissions).select_related('hospital__profile')) if m.source_submissions else []
  m.source_names=', '.join(s.hospital.profile.organization for s in sources) or 'Initial bundled model'
  models.append(m)
 return render(request,'admin_portal/model_history.html',{'models':models})

@guard
@require_POST
def activate_model(request,pk):
    gm=get_object_or_404(GlobalModel,pk=pk)
    GlobalModel.objects.filter(status='ACTIVE').update(status='AVAILABLE'); gm.status='ACTIVE'; gm.save(update_fields=['status'])
    messages.success(request,f'{gm.version} is now the model used by the Patient Portal.')
    return redirect('admin_model_history')
