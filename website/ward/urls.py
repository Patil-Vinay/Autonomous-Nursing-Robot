from django.urls import path

from ward import api, views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('robot/', views.later, {'title': 'Robot'}, name='robot'),
    path('ward/', views.later_nurse, {'title': 'Ward'}, name='ward'),
    path('schedule/', views.later_nurse, {'title': 'Schedule'}, name='schedule'),
    path('patients/', views.later, {'title': 'Patients'}, name='patients'),
    path('visits/', views.later, {'title': 'Visits'}, name='visits'),
    path('api/plan/', api.plan, name='api_plan'),
    path('api/visits/', api.visits, name='api_visits'),
    path('call/', views.later, {'title': 'Video call'}, name='call'),
]
