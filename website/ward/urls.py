from django.urls import path

from ward import api, views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('robot/', views.robot, name='robot'),
    path('ward/', views.ward, name='ward'),
    path('ward/<int:number>/admit/', views.admit, name='admit'),
    path('ward/<int:number>/discharge/', views.discharge, name='discharge'),
    path('schedule/', views.schedule, name='schedule'),
    path('schedule/add/', views.task_add, name='task_add'),
    path('schedule/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('schedule/give-now/', views.give_now, name='give_now'),
    path('schedule/hoppers/', views.hoppers, name='hoppers'),
    path('patients/', views.later, {'title': 'Patients'}, name='patients'),
    path('visits/', views.later, {'title': 'Visits'}, name='visits'),
    path('api/plan/', api.plan, name='api_plan'),
    path('api/visits/', api.visits, name='api_visits'),
    path('call/', views.later, {'title': 'Video call'}, name='call'),
]
