from django.shortcuts import render
from django.http import JsonResponse
import json

patient_data_queue = []


def home(request):
    return render(request, 'home.html', {'home_page': True})


def send_patient_info(request):
    if request.method == "POST":
        patient_data = json.loads(request.body)
        temperature = patient_data['temperature']
        heartrate = patient_data['heartrate']

        patient_data_queue.append({'temperature': temperature, 'heartrate': heartrate})
        return JsonResponse({'status': 'success'})
    return JsonResponse({'message': 'Use Post method to send data'})


def get_patient_info(request):
    if patient_data_queue:
        patient_data = patient_data_queue[0]
        patient_data_queue.pop(0)
        return JsonResponse(patient_data)
    return JsonResponse({'message': 'No new data!'})