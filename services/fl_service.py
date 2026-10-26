from pathlib import Path
import copy, gc, joblib, pandas as pd
from django.conf import settings
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from .ml_service import FEATURES, load_model, clear_model_cache

LOCAL_TREES=60
EXPECTED_CLIENTS=3
UPLOAD_DIR=Path(settings.MEDIA_ROOT)/'local_models'
UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
LABEL_NAMES={'N':'Normal','HY':'Hypertension','DI':'Diabetes','DI_HY':'Diabetes + Hypertension'}

def _split_three(X,y):
    try:
        X_train, X_tmp, y_train, y_tmp=train_test_split(X,y,test_size=.20,random_state=42,stratify=y)
        X_val, X_test, y_val, y_test=train_test_split(X_tmp,y_tmp,test_size=.50,random_state=42,stratify=y_tmp)
    except ValueError:
        X_train, X_tmp, y_train, y_tmp=train_test_split(X,y,test_size=.20,random_state=42)
        X_val, X_test, y_val, y_test=train_test_split(X_tmp,y_tmp,test_size=.50,random_state=42)
    return X_train,X_val,X_test,y_train,y_val,y_test

def train_local_model(csv_file,client_id,round_no):
    df=pd.read_csv(csv_file)
    missing=[c for c in FEATURES+['sublabel'] if c not in df.columns]
    if missing: raise ValueError('Missing columns: '+', '.join(missing))
    df=df.dropna(subset=FEATURES+['sublabel']).copy()
    if len(df)<30: raise ValueError('At least 30 valid records are required.')
    if df['sublabel'].nunique()<2: raise ValueError('The hospital dataset must contain at least 2 disease classes.')
    bundle=load_model(); pre=copy.deepcopy(bundle['pipeline'].named_steps['preprocessor']); encoder=bundle['label_encoder']
    X=df[FEATURES]; y=encoder.transform(df['sublabel'].astype(str))
    Xtr,Xval,Xte,ytr,yval,yte=_split_three(X,y)
    Xtrp=pre.transform(Xtr); Xvalp=pre.transform(Xval); Xtep=pre.transform(Xte)
    rf=RandomForestClassifier(n_estimators=LOCAL_TREES,max_features='sqrt',min_samples_leaf=2,bootstrap=True,random_state=42+round_no,n_jobs=1)
    rf.fit(Xtrp,ytr)
    val_pred=rf.predict(Xvalp); test_pred=rf.predict(Xtep)
    acc=float(accuracy_score(yte,test_pred)); f1=float(f1_score(yte,test_pred,average='macro'))
    distribution={LABEL_NAMES.get(str(k),str(k)):int(v) for k,v in df['sublabel'].value_counts().items()}
    path=UPLOAD_DIR/f'{client_id}_round_{round_no}.joblib'
    joblib.dump({'rf':rf,'records':len(df),'train_rows':len(Xtr),'validation_rows':len(Xval),'test_rows':len(Xte),'accuracy':acc,'validation_accuracy':float(accuracy_score(yval,val_pred)),'macro_f1':f1,'class_distribution':distribution,'client_id':client_id,'round_no':round_no,'trees':LOCAL_TREES},path,compress=3)
    return {'records':len(df),'train_rows':len(Xtr),'validation_rows':len(Xval),'test_rows':len(Xte),'accuracy':acc,'macro_f1':f1,'validation_accuracy':float(accuracy_score(yval,val_pred)),'class_distribution':distribution,'trees':LOCAL_TREES,'path':str(path)}

def aggregate(round_no,submissions):
    if len(submissions)!=EXPECTED_CLIENTS: raise ValueError(f'Exactly {EXPECTED_CLIENTS} unique hospital updates are required.')
    bundles=[joblib.load(s['path']) for s in submissions]
    if any(len(b['rf'].estimators_)!=LOCAL_TREES for b in bundles): raise ValueError('Every hospital update must contain exactly 60 trees.')
    base=copy.deepcopy(bundles[0]['rf']); trees=[]
    for b in bundles: trees.extend(b['rf'].estimators_)
    base.estimators_=trees; base.n_estimators=len(trees)
    global_bundle=load_model(); new_bundle=copy.deepcopy(global_bundle); new_bundle['pipeline'].steps[-1]=('classifier',base); new_bundle['model_version']=f'v{round_no+1}.0.0'; new_bundle['aggregation']={'round':round_no,'clients':EXPECTED_CLIENTS,'trees_per_client':LOCAL_TREES,'global_trees':len(trees)}
    out=Path(settings.MEDIA_ROOT)/f'global_model_round_{round_no}.joblib'; joblib.dump(new_bundle,out,compress=3); clear_model_cache(); tree_count=len(trees)
    del bundles,base,trees,new_bundle; gc.collect(); return str(out),tree_count
