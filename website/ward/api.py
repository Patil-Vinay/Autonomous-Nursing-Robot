"""JSON API for the robot's web_link node.

Every request carries the robot token: Authorization: Bearer <SCOBO_ROBOT_TOKEN>.
Times from the robot are ward local time without a zone, the same TIME_ZONE as the site.

GET  api/plan/     beds and tasks, with the field names of scobo_interfaces/WardPlan
GET  api/visits/   {"last": highest robot_id stored}
POST api/visits/   {"visits": [rows of the robot's ward.db]}, a row sent twice is stored once
"""
import hmac
import json
from datetime import datetime
from functools import wraps

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ward.models import Bed, Patient, Task, Visit


def robot_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        sent = request.headers.get('Authorization', '').encode()
        if not hmac.compare_digest(sent, f'Bearer {settings.ROBOT_TOKEN}'.encode()):
            return JsonResponse({'error': 'bad token'}, status=401)
        return view(request, *args, **kwargs)
    # the robot has no session, so no CSRF cookie either
    return csrf_exempt(wrapped)


@robot_only
def plan(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET only'}, status=405)
    occupied = set(Patient.objects.filter(discharged__isnull=True).values_list('bed', flat=True))
    beds = [{'number': b.number, 'occupied': b.number in occupied} for b in Bed.objects.all()]
    tasks = [{
        'id': t.task_id, 'bed': t.bed, 'time': t.time.strftime('%H:%M'), 'daily': t.daily,
        'temperature': t.temperature, 'pulse_oximeter': t.pulse_oximeter,
        'hopper': t.hopper_id or 0, 'count': t.count,
    } for t in Task.objects.all()]
    return JsonResponse({'beds': beds, 'tasks': tasks})


def patient_at(bed, day):
    """The patient who was in the bed on that day."""
    return (Patient.objects.filter(bed_id=bed, admitted__lte=day)
            .filter(Q(discharged__isnull=True) | Q(discharged__gte=day))
            .order_by('-admitted').first())


def store(row):
    """Returns True when the row is new."""
    time = datetime.fromisoformat(row['time'])
    if timezone.is_naive(time):
        time = timezone.make_aware(time)
    _, created = Visit.objects.get_or_create(robot_id=int(row['id']), defaults={
        'time': time,
        'trip': row.get('trip') or '',
        'bed': int(row['bed']),
        'patient': patient_at(int(row['bed']), timezone.localdate(time)),
        'tasks': ','.join(row.get('tasks') or []),
        # the robot sends 0 for a reading it did not take
        'temperature': row.get('temperature') or None,
        'heart_rate': row.get('heart_rate') or None,
        'spo2': row.get('spo2') or None,
        'pills': int(row.get('pills') or 0),
        'collected': bool(row.get('collected')),
        'status': row['status'],
    })
    return created


@robot_only
def visits(request):
    if request.method == 'GET':
        return JsonResponse({'last': Visit.objects.aggregate(last=Max('robot_id'))['last'] or 0})
    if request.method != 'POST':
        return JsonResponse({'error': 'GET or POST only'}, status=405)
    try:
        rows = json.loads(request.body)['visits']
        with transaction.atomic():
            stored = sum(store(row) for row in rows)
    except (ValueError, KeyError, TypeError) as e:
        return JsonResponse({'error': f'bad visit data: {e}'}, status=400)
    return JsonResponse({'stored': stored})
