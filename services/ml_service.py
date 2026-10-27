from pathlib import Path
import re, joblib, pandas as pd, numpy as np
from django.conf import settings

BASE_MODEL_PATH=Path(settings.BASE_DIR)/'ml_models'/'chronic_disease_rf.joblib'
NUMERICAL=['age','age_normalized','bmi','HbA1c_level','glucose','cholesterol','sleep_hours','triglycerides','blood_pressure','crp_level','homocysteine_level','systolic_bp','diastolic_bp','alcohol_intake','salt_intake','heart_rate','hdl','ldl']
CATEGORICAL=['age_level','gender','bmi_level','smoking','physical_activity','family_history','stress_level','low_hdl_cholesterol','high_ldl_cholesterol','high_blood_pressure','sugar_consumption','education_level','employment_status']
FEATURES=NUMERICAL+CATEGORICAL
CLASSES=['DI','DI_HY','HY','N']
DISPLAY_CLASSES={'N':'Normal','DI':'Diabetes','HY':'Hypertension','DI_HY':'Diabetes + Hypertension'}
_model_cache=None; _model_cache_path=None; _model_cache_mtime=None

def _registry_active_path():
    """Use the active superset if selected; otherwise use the active global version."""
    try:
        from hospital.models import GlobalModel, SupersetModel
        supermodel = SupersetModel.objects.filter(is_active=True).order_by('-created_at').first()
        if supermodel:
            path = Path(settings.BASE_DIR) / supermodel.artifact_path if not Path(supermodel.artifact_path).is_absolute() else Path(supermodel.artifact_path)
            if path.exists():
                return path
        obj = GlobalModel.objects.filter(status='ACTIVE').order_by('-round_no', '-created_at').first()
        if obj:
            path = Path(settings.BASE_DIR) / obj.artifact_path if not Path(obj.artifact_path).is_absolute() else Path(obj.artifact_path)
            if path.exists():
                return path
    except Exception:
        pass
    return BASE_MODEL_PATH

def _latest_model_path():
    return _registry_active_path()

def clear_model_cache():
    global _model_cache,_model_cache_path,_model_cache_mtime
    _model_cache=_model_cache_path=_model_cache_mtime=None

def load_model():
    global _model_cache,_model_cache_path,_model_cache_mtime
    path=_latest_model_path(); mtime=path.stat().st_mtime_ns
    if _model_cache is None or _model_cache_path!=path or _model_cache_mtime!=mtime:
        _model_cache=joblib.load(path); _model_cache_path=path; _model_cache_mtime=mtime
    return _model_cache

def predict_one(payload):
    bundle=load_model(); pipe=bundle['pipeline']; encoder=bundle['label_encoder']; frame=pd.DataFrame([{k:payload[k] for k in FEATURES}]); pred_code=int(pipe.predict(frame)[0]); probs=pipe.predict_proba(frame)[0]; labels=encoder.inverse_transform(np.arange(len(probs))); probability_map={str(label):float(prob) for label,prob in zip(labels,probs)}; label=str(encoder.inverse_transform([pred_code])[0]); return label,float(np.max(probs)),probability_map

def model_info():
    path = _latest_model_path()
    info = {'version': 'v1.0.0', 'trees': 180, 'processed_features': 55,
            'classes': CLASSES, 'display_classes': [DISPLAY_CLASSES[x] for x in CLASSES],
            'artifact': path.name, 'created_at': None, 'status': 'ACTIVE',
            'model_type': 'Global model', 'model_name': 'Initial bundled model'}
    try:
        from hospital.models import GlobalModel, SupersetModel
        supermodel = SupersetModel.objects.filter(is_active=True).order_by('-created_at').first()
        if supermodel:
            spath = Path(settings.BASE_DIR) / supermodel.artifact_path if not Path(supermodel.artifact_path).is_absolute() else Path(supermodel.artifact_path)
            if spath.exists():
                info.update({'version': supermodel.version, 'trees': supermodel.trees,
                             'created_at': supermodel.created_at, 'status': 'ACTIVE',
                             'model_type': 'Superset model', 'model_name': supermodel.name,
                             'artifact': spath.name})
                return info
        obj = GlobalModel.objects.filter(status='ACTIVE').order_by('-round_no', '-created_at').first()
        if obj:
            info.update({'version': obj.version, 'trees': obj.trees, 'created_at': obj.created_at,
                         'status': obj.status, 'model_type': 'Global model', 'model_name': obj.version,
                         'artifact': path.name})
    except Exception:
        pass
    return info
