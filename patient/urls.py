from django.urls import path
from .views import dashboard,predict,history,detail
urlpatterns=[path('',dashboard,name='patient_dashboard'),path('predict/',predict,name='patient_predict'),path('history/',history,name='patient_history'),path('history/<int:prediction_id>/',detail,name='patient_prediction_detail')]
