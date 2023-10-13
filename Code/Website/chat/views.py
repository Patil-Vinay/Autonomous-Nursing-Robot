from django.shortcuts import render
from django.http import JsonResponse
from agora_token_builder import RtcTokenBuilder
import time
import os
import json

uid = 1
movement_queue = []


def get_token(request):
    global uid
    uid += 1
    app_id = os.getenv('APP_ID')
    app_certificate = os.getenv('APP_CERTIFICATE')
    channel_name = 'main'
    expiration_time_in_secs = 3600 * 24
    current_time = time.time()
    privilege_expired_time = current_time + expiration_time_in_secs
    role = 1

    token = RtcTokenBuilder.buildTokenWithUid(app_id, app_certificate, channel_name, uid, role, privilege_expired_time)
    return JsonResponse({'token': token, 'uid': uid}, safe=False)


def get_movements(request):
    if movement_queue:
        movement_data = movement_queue[0]
        movement_queue.pop(0)
        return JsonResponse(movement_data)
    return JsonResponse({'rotate': 0, 'tilt': 0, 'reset': 0})


def send_movements(request):
    if request.method == "POST":
        movement_data = json.loads(request.body)
        rotation = movement_data['rotate']
        tilt = movement_data['tilt']
        reset = movement_data['reset']

        movement_queue.append({'rotate': rotation, 'tilt': tilt, 'reset': reset})
        return JsonResponse({'status': 'success'})
    return JsonResponse({'message': 'Use Post method to send data'})


def get_app_id(request):
    app_id = os.getenv("APP_ID")
    return JsonResponse({'app_id': app_id})


def chat(request):
    return render(request, 'chat.html')


def join(request):
    return render(request, 'join.html', {'video_chat_page': True})
