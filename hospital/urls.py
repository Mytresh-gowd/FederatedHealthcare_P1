from django.urls import path
from .views import dashboard,upload,submit,history,detail
urlpatterns=[path('',dashboard,name='hospital_dashboard'),path('upload/',upload,name='hospital_upload'),path('submit/<int:submission_id>/',submit,name='hospital_submit'),path('history/',history,name='hospital_history'),path('history/<int:submission_id>/',detail,name='hospital_submission_detail')]
