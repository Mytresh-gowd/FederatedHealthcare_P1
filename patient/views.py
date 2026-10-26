from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect,get_object_or_404
from services.ml_service import FEATURES,predict_one,model_info,DISPLAY_CLASSES
from .models import Prediction

PATIENT_FIELDS={'age':('Age (years)','number',''),'gender':('Gender','select',''),'height_cm':('Height (cm)','number','Used to calculate BMI.'),'weight_kg':('Weight (kg)','number','Used to calculate BMI.'),'HbA1c_level':('HbA1c level','number','From a recent blood report.'),'glucose':('Glucose','number','From a recent blood report.'),'cholesterol':('Total cholesterol','number','From a recent blood report.'),'sleep_hours':('Sleep hours','number','Average hours per day.'),'triglycerides':('Triglycerides','number','From a recent blood report.'),'crp_level':('CRP level','number','From a recent blood report.'),'homocysteine_level':('Homocysteine level','number','From a recent blood report.'),'systolic_bp':('Systolic blood pressure','number','From a recent BP reading.'),'diastolic_bp':('Diastolic blood pressure','number','From a recent BP reading.'),'alcohol_intake':('Alcohol intake','number','Use the unit shown in your report.'),'salt_intake':('Salt intake','number','Use the unit shown in your report.'),'heart_rate':('Heart rate','number','Beats per minute.'),'hdl':('HDL cholesterol','number','From a recent blood report.'),'ldl':('LDL cholesterol','number','From a recent blood report.'),'smoking':('Smoking','select',''),'physical_activity':('Physical activity','select',''),'family_history':('Family history','select',''),'stress_level':('Stress level','select',''),'sugar_consumption':('Sugar consumption','select',''),'education_level':('Education level','select',''),'employment_status':('Employment status','select','')}
OPTIONS={'gender':['Female','Male'],'smoking':['Never','Former','Current'],'physical_activity':['Low','Moderate','High'],'family_history':['No','Yes'],'stress_level':['Low','Moderate','High'],'sugar_consumption':['Low','Moderate','High'],'education_level':['Primary','Secondary','Tertiary'],'employment_status':['Student','Employed','Self-employed','Unemployed']}
LABELS=DISPLAY_CLASSES

def patient_only(view):
 @wraps(view)
 def wrapped(request,*args,**kwargs):
  p=getattr(request.user,'profile',None)
  if not request.user.is_authenticated or (p and p.role!='PATIENT'): return redirect('dashboard')
  return view(request,*args,**kwargs)
 return wrapped

def _float(post,key,min_value=None,max_value=None):
 v=post.get(key,'').strip()
 if not v: raise ValueError(f'Please enter {PATIENT_FIELDS[key][0]}.')
 try: x=float(v)
 except ValueError: raise ValueError(f'{PATIENT_FIELDS[key][0]} must be a number.')
 if min_value is not None and x<min_value: raise ValueError(f'{PATIENT_FIELDS[key][0]} cannot be negative.')
 if max_value is not None and x>max_value: raise ValueError(f'{PATIENT_FIELDS[key][0]} is outside the supported range.')
 return x

def _build_model_payload(post):
 age=_float(post,'age',18,85); height=_float(post,'height_cm',50,250); weight=_float(post,'weight_kg',2,300); bmi=weight/((height/100)**2)
 if not 10<=bmi<=80: raise ValueError('Calculated BMI is outside the supported range. Please check height and weight.')
 age_level='Young' if age<30 else 'Adult' if age<45 else 'Middle' if age<60 else 'Senior'; bmi_level='Underweight' if bmi<18.5 else 'Normal' if bmi<25 else 'Overweight' if bmi<30 else 'Obese'
 systolic=_float(post,'systolic_bp',1,300); diastolic=_float(post,'diastolic_bp',1,200); hdl=_float(post,'hdl',0,300); ldl=_float(post,'ldl',0,500)
 payload={'age':age,'age_normalized':(age-18)/67,'bmi':bmi,'HbA1c_level':_float(post,'HbA1c_level',0,30),'glucose':_float(post,'glucose',0,1000),'cholesterol':_float(post,'cholesterol',0,1000),'sleep_hours':_float(post,'sleep_hours',0,24),'triglycerides':_float(post,'triglycerides',0,2000),'blood_pressure':(systolic+diastolic)/2,'crp_level':_float(post,'crp_level',0,1000),'homocysteine_level':_float(post,'homocysteine_level',0,200),'systolic_bp':systolic,'diastolic_bp':diastolic,'alcohol_intake':_float(post,'alcohol_intake',0,100),'salt_intake':_float(post,'salt_intake',0,100),'heart_rate':_float(post,'heart_rate',1,250),'hdl':hdl,'ldl':ldl,'age_level':age_level,'gender':post.get('gender',''),'bmi_level':bmi_level,'smoking':post.get('smoking',''),'physical_activity':post.get('physical_activity',''),'family_history':post.get('family_history',''),'stress_level':post.get('stress_level',''),'low_hdl_cholesterol':'Yes' if hdl<45 else 'No','high_ldl_cholesterol':'Yes' if ldl>=130 else 'No','high_blood_pressure':'Yes' if systolic>=130 or diastolic>=80 else 'No','sugar_consumption':post.get('sugar_consumption',''),'education_level':post.get('education_level',''),'employment_status':post.get('employment_status','')}
 for key in ['gender','smoking','physical_activity','family_history','stress_level','sugar_consumption','education_level','employment_status']:
  if payload[key] not in OPTIONS[key]: raise ValueError(f'Please select a valid {PATIENT_FIELDS[key][0]}.')
 return payload

@login_required
@patient_only
def dashboard(request):
 history=Prediction.objects.filter(patient=request.user); last=history.first()
 return render(request,'patient/dashboard.html',{'history':history[:5],'last':last,'model':model_info(),'labels':LABELS})

@login_required
@patient_only
def predict(request):
 result=None; error=None
 if request.method=='POST':
  try:
   payload=_build_model_payload(request.POST); label,confidence,probs=predict_one(payload); info=model_info(); Prediction.objects.create(patient=request.user,prediction=LABELS.get(label,label),confidence=confidence,probabilities=probs,input_snapshot=payload,model_version=info['version']); result={'label':LABELS.get(label,label),'confidence':confidence,'probs':{LABELS.get(k,k):v for k,v in probs.items()},'version':info['version']}
  except Exception as exc: error=str(exc)
 fields=[(k,v[0],v[1],v[2],OPTIONS.get(k,[])) for k,v in PATIENT_FIELDS.items()]
 return render(request,'patient/predict.html',{'result':result,'error':error,'fields':fields,'model':model_info()})

@login_required
@patient_only
def history(request): return render(request,'patient/history.html',{'items':Prediction.objects.filter(patient=request.user),'labels':LABELS})

@login_required
@patient_only
def detail(request,prediction_id): return render(request,'patient/detail.html',{'item':get_object_or_404(Prediction,id=prediction_id,patient=request.user),'labels':LABELS})
