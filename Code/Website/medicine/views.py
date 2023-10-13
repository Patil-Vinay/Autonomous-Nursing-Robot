from django.shortcuts import render
from django.http import JsonResponse

medicine_queue = []

def pill_dispenser(request):
    if request.method == "POST":
        medicine = request.POST.get("medicine")
        medicine_queue.append(medicine)
    return render(request, 'pill-dispenser.html', {'dispenser_page': True})


def about(request):
    return render(request, 'about.html', {'about_page': True})


def get_medicine(request):
    if medicine_queue:
        medicine = medicine_queue[0]
        medicine_queue.pop(0)
        return JsonResponse({"medicine": medicine})
    return JsonResponse({"medicine": 0})