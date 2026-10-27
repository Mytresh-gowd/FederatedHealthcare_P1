from pathlib import Path
import copy
import joblib
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from patient.models import Prediction
from hospital.models import Submission, FederatedRound, GlobalModel, SupersetModel
from services.ml_service import model_info, clear_model_cache
from services.fl_service import aggregate, UPLOAD_DIR, LOCAL_TREES, EXPECTED_CLIENTS


def staff(u):
    return u.is_authenticated and (u.is_staff or getattr(getattr(u, 'profile', None), 'role', None) == 'ADMIN')


def guard(view):
    return user_passes_test(staff, login_url='/login/')(view)


@guard
def dashboard(request):
    latest = GlobalModel.objects.order_by('-round_no', '-created_at').first()
    active = GlobalModel.objects.filter(status='ACTIVE').first()
    active_superset = SupersetModel.objects.filter(is_active=True).first()
    open_round = FederatedRound.objects.filter(status='OPEN').order_by('-round_no').first()
    pending = Submission.objects.filter(status='SUBMITTED').select_related('hospital__profile').order_by('-submitted_at', '-created_at')
    return render(request, 'admin_portal/dashboard.html', {
        'latest': latest, 'active': active, 'active_superset': active_superset,
        'open_round': open_round, 'pending': pending,
        'patients': User.objects.filter(profile__role='PATIENT').count(),
        'predictions': Prediction.objects.count(),
        'hospital_count': User.objects.filter(profile__role='HOSPITAL').count(),
        'model': model_info(), 'expected_clients': EXPECTED_CLIENTS,
    })


@guard
def hospitals(request):
    return render(request, 'admin_portal/hospitals.html', {'items': Submission.objects.select_related('hospital__profile').order_by('-created_at')})


@guard
def patients(request):
    return render(request, 'admin_portal/patients.html', {'items': Prediction.objects.select_related('patient').order_by('-created_at')})


@guard
def rounds(request):
    items = FederatedRound.objects.all().order_by('-round_no')
    pending = {}
    for r in items:
        qs = Submission.objects.filter(round_no=r.round_no, status='SUBMITTED').select_related('hospital__profile')
        unique = {}
        for s in qs:
            unique.setdefault(s.hospital_id, s)
        pending[r.round_no] = list(unique.values())
    return render(request, 'admin_portal/rounds.html', {'items': items, 'pending': pending, 'expected_clients': EXPECTED_CLIENTS, 'local_trees': LOCAL_TREES, 'model': model_info()})


@guard
@require_POST
def aggregate_round(request, round_no):
    rnd = get_object_or_404(FederatedRound, round_no=round_no)
    if rnd.status != 'OPEN':
        messages.info(request, 'This round is already completed.')
        return redirect('admin_rounds')
    selected_ids = [int(x) for x in request.POST.getlist('submission_ids') if x.isdigit()]
    subs = list(Submission.objects.filter(id__in=selected_ids, round_no=round_no, status='SUBMITTED').select_related('hospital__profile'))
    unique = {}
    for s in subs:
        unique.setdefault(s.hospital_id, s)
    subs = list(unique.values())
    hospital_ids = {s.hospital.profile.client_id or s.hospital.username for s in subs}
    if len(subs) != EXPECTED_CLIENTS or len(hospital_ids) != EXPECTED_CLIENTS:
        messages.error(request, f'Select exactly one submitted update from each of Hospital 1, Hospital 2 and Hospital 3. Selected: {len(subs)}.')
        return redirect('admin_rounds')
    bundle = []
    for s in subs:
        cid = s.hospital.profile.client_id or s.hospital.username
        path = UPLOAD_DIR / f'{cid}_round_{round_no}.joblib'
        if not path.exists():
            messages.error(request, f'Model artifact for {s.hospital.profile.organization} is missing. Retrain that hospital.')
            return redirect('admin_rounds')
        bundle.append({'path': str(path)})
    try:
        out, trees = aggregate(round_no, bundle)
        acc = sum((s.accuracy or 0) for s in subs) / len(subs)
        f1 = sum((s.macro_f1 or 0) for s in subs) / len(subs)
        version = f'v{round_no + 1}.0.0'
        with transaction.atomic():
            GlobalModel.objects.filter(status='ACTIVE').update(status='AVAILABLE')
            SupersetModel.objects.filter(is_active=True).update(is_active=False)
            gm = GlobalModel.objects.create(version=version, round_no=round_no, trees=trees, accuracy=acc,
                macro_f1=f1, source_submissions=[s.id for s in subs],
                artifact_path=str(Path(out).relative_to(Path(settings.BASE_DIR))), status='ACTIVE')
            Submission.objects.filter(id__in=[s.id for s in subs]).update(status='AGGREGATED')
            rnd.clients = len(subs); rnd.trees_per_client = LOCAL_TREES; rnd.global_trees = trees
            rnd.global_model_version = version; rnd.status = 'COMPLETED'; rnd.completed_at = timezone.now(); rnd.save()
            FederatedRound.objects.get_or_create(round_no=round_no + 1, defaults={'clients': 0, 'trees_per_client': LOCAL_TREES, 'global_trees': EXPECTED_CLIENTS * LOCAL_TREES, 'status': 'OPEN'})
        clear_model_cache()
        messages.success(request, f'{gm.version} created from all three hospital clients and activated for the Patient Portal.')
    except Exception as exc:
        messages.error(request, f'Aggregation failed: {exc}')
    return redirect('admin_dashboard')


@guard
def model_history(request):
    models = []
    for m in GlobalModel.objects.all():
        sources = list(Submission.objects.filter(id__in=m.source_submissions).select_related('hospital__profile')) if m.source_submissions else []
        m.source_names = ', '.join(s.hospital.profile.organization for s in sources) or 'Initial bundled model'
        models.append(m)
    return render(request, 'admin_portal/model_history.html', {'models': models, 'active_model': model_info()})


@guard
@require_POST
def activate_model(request, pk):
    gm = get_object_or_404(GlobalModel, pk=pk)
    with transaction.atomic():
        GlobalModel.objects.filter(status='ACTIVE').update(status='AVAILABLE')
        SupersetModel.objects.filter(is_active=True).update(is_active=False)
        gm.status = 'ACTIVE'
        gm.save(update_fields=['status'])
    clear_model_cache()
    messages.success(request, f'{gm.version} is now the model used by the Patient Portal.')
    return redirect('admin_model_history')


@guard
def superset_models(request):
    return render(request, 'admin_portal/superset_models.html', {
        'global_models': GlobalModel.objects.all().order_by('-round_no', '-created_at'),
        'superset_models': SupersetModel.objects.all(),
        'active_model': model_info(),
    })


@guard
@require_POST
def create_superset_model(request):
    selected_ids = list(dict.fromkeys(int(x) for x in request.POST.getlist('global_model_ids') if x.isdigit()))
    name = (request.POST.get('name') or '').strip()[:120]
    if not name:
        messages.error(request, 'Enter a name for the superset model.')
        return redirect('admin_superset_models')
    if len(selected_ids) < 2:
        messages.error(request, 'Select at least two global model versions to create a superset.')
        return redirect('admin_superset_models')
    selected = list(GlobalModel.objects.filter(id__in=selected_ids).order_by('round_no', 'created_at'))
    if len(selected) != len(selected_ids):
        messages.error(request, 'One or more selected global versions could not be found.')
        return redirect('admin_superset_models')
    try:
        bundles = []
        for gm in selected:
            artifact = Path(gm.artifact_path)
            if not artifact.is_absolute():
                artifact = Path(settings.BASE_DIR) / artifact
            if not artifact.exists():
                raise ValueError(f'Artifact for {gm.version} is missing: {artifact.name}')
            bundle = joblib.load(artifact)
            if 'pipeline' not in bundle or 'label_encoder' not in bundle:
                raise ValueError(f'{gm.version} does not contain a compatible model pipeline.')
            classifier = bundle['pipeline'].named_steps.get('classifier')
            if classifier is None or not hasattr(classifier, 'estimators_'):
                raise ValueError(f'{gm.version} is not a trained Random Forest model.')
            bundles.append((gm, bundle, classifier))
        first_classes = list(bundles[0][2].classes_)
        first_features = getattr(bundles[0][2], 'n_features_in_', None)
        for gm, bundle, classifier in bundles[1:]:
            if list(classifier.classes_) != first_classes or getattr(classifier, 'n_features_in_', None) != first_features:
                raise ValueError(f'{gm.version} uses a different class/feature schema. Only compatible versions can be combined.')
        combined_bundle = copy.deepcopy(bundles[0][1])
        combined_rf = copy.deepcopy(bundles[0][2])
        combined_estimators = []
        for gm, bundle, classifier in bundles:
            combined_estimators.extend(classifier.estimators_)
        combined_rf.estimators_ = combined_estimators
        combined_rf.n_estimators = len(combined_estimators)
        combined_bundle['pipeline'].steps[-1] = ('classifier', combined_rf)
        version_number = SupersetModel.objects.count() + 1
        version = f'SM-v{version_number}'
        while SupersetModel.objects.filter(version=version).exists():
            version_number += 1
            version = f'SM-v{version_number}'
        combined_bundle['model_version'] = version
        combined_bundle['aggregation'] = {
            'type': 'superset', 'source_versions': [gm.version for gm, _, _ in bundles],
            'global_trees': len(combined_estimators), 'created_at': timezone.now().isoformat(),
        }
        output_dir = Path(settings.MEDIA_ROOT) / 'superset_models'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'{version.replace("/", "_")}.joblib'
        joblib.dump(combined_bundle, output_path, compress=3)
        relative_path = str(output_path.relative_to(Path(settings.BASE_DIR)))
        with transaction.atomic():
            superset = SupersetModel.objects.create(name=name, version=version,
                source_versions=[gm.version for gm, _, _ in bundles], trees=len(combined_estimators),
                artifact_path=relative_path, is_active=False)
        messages.success(request, f'{superset.name} ({superset.version}) created with {superset.trees} trees from {len(selected)} global versions. It is available but not active until you choose Use for Patient Portal.')
    except Exception as exc:
        messages.error(request, f'Superset creation failed: {exc}')
    return redirect('admin_superset_models')


@guard
@require_POST
def activate_superset_model(request, pk):
    sm = get_object_or_404(SupersetModel, pk=pk)
    artifact = Path(sm.artifact_path)
    if not artifact.is_absolute():
        artifact = Path(settings.BASE_DIR) / artifact
    if not artifact.exists():
        messages.error(request, 'This superset model artifact is missing. It cannot be activated.')
        return redirect('admin_superset_models')
    with transaction.atomic():
        GlobalModel.objects.filter(status='ACTIVE').update(status='AVAILABLE')
        SupersetModel.objects.filter(is_active=True).update(is_active=False)
        sm.is_active = True
        sm.save(update_fields=['is_active'])
    clear_model_cache()
    messages.success(request, f'{sm.name} ({sm.version}) is now used by the Patient Portal. Individual global versions remain available for rollback.')
    return redirect('admin_superset_models')
