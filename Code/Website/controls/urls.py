from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('send-patient-info/', views.send_patient_info),
    path('get-patient-info/', views.get_patient_info),
]