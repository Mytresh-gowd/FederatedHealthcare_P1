from django.urls import path
from .views import dashboard, hospitals, patients, rounds, aggregate_round, model_history, activate_model, superset_models, create_superset_model, activate_superset_model

urlpatterns = [
    path('', dashboard, name='admin_dashboard'),
    path('hospitals/', hospitals, name='admin_hospitals'),
    path('patients/', patients, name='admin_patients'),
    path('rounds/', rounds, name='admin_rounds'),
    path('rounds/<int:round_no>/aggregate/', aggregate_round, name='admin_aggregate_round'),
    path('models/', model_history, name='admin_model_history'),
    path('models/<int:pk>/activate/', activate_model, name='admin_activate_model'),
    path('superset-models/', superset_models, name='admin_superset_models'),
    path('superset-models/create/', create_superset_model, name='admin_create_superset_model'),
    path('superset-models/<int:pk>/activate/', activate_superset_model, name='admin_activate_superset_model'),
]
