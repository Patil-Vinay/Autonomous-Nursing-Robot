from django.urls import path
from . import views

urlpatterns = [
    path('dispenser/', views.pill_dispenser, name='pill_dispenser'),
    path('about/', views.about, name='about'),
    path('get-medicine/', views.get_medicine),
]
