from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat, name='video_chat'),
    path('join/', views.join, name='video_chat_join'),
    path('get_token/', views.get_token),
    path('get_app_id/', views.get_app_id),
    path('get-movements/', views.get_movements),
    path('send-movements/', views.send_movements),
]
