from django.shortcuts import render
from django.utils import timezone

from ward.models import Bed, Task, Visit
from ward.roles import nurse_required, staff_required

# beds as they stand in the room, as on the robot's map: 5 to 8 on top, 4 to 1 below
ROOM_ORDER = [5, 6, 7, 8, 4, 3, 2, 1]


@staff_required
def dashboard(request):
    beds = {b.number: b for b in Bed.objects.all()}
    today = timezone.localdate()
    return render(request, 'ward/dashboard.html', {
        'page': 'dashboard',
        'beds': [beds[n] for n in ROOM_ORDER if n in beds],
        'occupied': sum(b.occupied for b in beds.values()),
        'tasks_today': Task.objects.count(),
        'visits_today': Visit.objects.filter(time__date=today).count(),
        'problems_today': Visit.objects.filter(time__date=today).exclude(status='done').count(),
    })


# pages not built yet

def _later(request, title):
    context = {'page': request.resolver_match.url_name, 'title': title}
    return render(request, 'ward/later.html', context)


@staff_required
def later(request, title):
    return _later(request, title)


@nurse_required
def later_nurse(request, title):
    return _later(request, title)
