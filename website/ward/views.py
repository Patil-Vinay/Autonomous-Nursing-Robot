import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ward.forms import AdmitForm, GiveNowForm, TaskForm
from ward.layout import layout
from ward.models import Bed, Hopper, Patient, Task, Visit
from ward.roles import nurse_required, staff_required

# beds as they stand in the room, as on the robot's map: 5 to 8 on top, 4 to 1 below
ROOM_ORDER = [5, 6, 7, 8, 4, 3, 2, 1]

# window_minutes of the task manager
TRIP_WINDOW = timedelta(minutes=15)

# (field, label, unit, decimals, low, high), a reading outside low..high needs a look
VITALS = [
    ('temperature', 'Temp', '°C', 1, 35.5, 37.5),
    ('heart_rate', 'Pulse', 'bpm', 0, 50, 100),
    ('spo2', 'SpO2', '%', 0, 94, 100),
]


def room_beds():
    beds = {b.number: b for b in Bed.objects.all()}
    return [beds[n] for n in ROOM_ORDER if n in beds]


@staff_required
def dashboard(request):
    beds = room_beds()
    today = timezone.localdate()
    return render(request, 'ward/dashboard.html', {
        'page': 'dashboard',
        'beds': beds,
        'occupied': sum(b.occupied for b in beds),
        'tasks_today': Task.objects.count(),
        'visits_today': Visit.objects.filter(time__date=today).count(),
        'problems_today': Visit.objects.filter(time__date=today).exclude(status='done').count(),
    })


# robot page, the browser talks to the robot's rosbridge

@staff_required
def robot(request):
    now = timezone.localtime().time()
    ever, today = task_states()
    up_next = []
    for task in Task.objects.select_related('hopper').filter(time__gte=now):
        if not (today if task.daily else ever).get(task.task_id):
            task.label = task_label(task)
            up_next.append(task)
    states = {}
    for bed in room_beds():
        person = bed.patient
        if not person:
            states[bed.number] = {'occupied': False}
            continue
        last = Visit.objects.filter(patient=person).order_by('-time').first()
        alert = any(v['out'] for v in latest_vitals(person)) or bool(last and not last.ok)
        states[bed.number] = {'occupied': True, 'initials': person.initials, 'alert': alert}
    return render(request, 'ward/robot.html', {
        'page': 'robot',
        'robot_ws': settings.ROBOT_WS,
        'layout': layout(states),
        'beds': room_beds(),
        'up_next': up_next[:4],
        'last_visit': Visit.objects.first(),
    })


# ward page: admit and discharge

def latest_vitals(patient):
    vitals = []
    for field, label, unit, decimals, low, high in VITALS:
        visit = (Visit.objects.filter(patient=patient, **{f'{field}__isnull': False})
                 .order_by('-time').first())
        value = getattr(visit, field) if visit else None
        vitals.append({
            'label': label, 'unit': unit, 'value': value, 'decimals': decimals,
            'time': visit.time if visit else None,
            'out': value is not None and not low <= value <= high,
        })
    return vitals


def ward_page(request, admit_bed=None, form=None):
    cards = []
    for bed in room_beds():
        patient = bed.patient
        cards.append({'bed': bed, 'patient': patient,
                      'vitals': latest_vitals(patient) if patient else []})
    return render(request, 'ward/ward.html', {
        'page': 'ward', 'cards': cards, 'admit_bed': admit_bed, 'form': form})


@nurse_required
def ward(request):
    # ?admit=<bed> opens the admit form beside the beds
    number = request.GET.get('admit', '')
    bed = Bed.objects.filter(number=int(number)).first() if number.isdigit() else None
    if bed and not bed.occupied:
        return ward_page(request, bed, AdmitForm())
    return ward_page(request)


@nurse_required
@require_POST
def admit(request, number):
    bed = get_object_or_404(Bed, number=number)
    if bed.occupied:
        messages.error(request, f'Bed {number} already has a patient.')
        return redirect('ward')
    form = AdmitForm(request.POST)
    if not form.is_valid():
        return ward_page(request, bed, form)
    patient = form.save(commit=False)
    patient.bed = bed
    patient.save()
    messages.success(request, f'{patient.name} admitted to bed {number}. '
                              'The robot gets the new plan within a few seconds.')
    return redirect('ward')


@nurse_required
@require_POST
def discharge(request, number):
    bed = get_object_or_404(Bed, number=number)
    patient = bed.patient
    if patient:
        patient.discharged = timezone.localdate()
        patient.save()
        messages.success(request, f'{patient.name} discharged from bed {number}. '
                                  'The robot skips this bed from now on.')
    return redirect('ward')


# schedule page: tasks, hopper names and medicine now

def task_label(task):
    jobs = []
    if task.temperature:
        jobs.append('temperature')
    if task.pulse_oximeter:
        jobs.append('pulse oximeter')
    if task.hopper_id:
        medicine = task.hopper.medicine or f'hopper {task.hopper_id}'
        jobs.append(f'{task.count} x {medicine}')
    return ', '.join(jobs)


def task_states():
    """Last visit record of each task id, all time and today."""
    today = timezone.localdate()
    ever, now = {}, {}
    for visit in Visit.objects.order_by('time'):
        for task_id in filter(None, visit.tasks.split(',')):
            ever[task_id] = visit
            if timezone.localdate(visit.time) == today:
                now[task_id] = visit
    return ever, now


def trips(tasks):
    """Groups the tasks into trips the same way as the task manager."""
    groups = []
    for task in tasks:
        at = datetime.combine(datetime.min, task.time)
        if groups and at <= groups[-1]['start'] + TRIP_WINDOW:
            groups[-1]['tasks'].append(task)
        else:
            groups.append({'start': at, 'tasks': [task]})
    return groups


def new_task_id(task):
    where = f'bed{task.bed}' if task.bed else 'round'
    what = 'pills' if task.hopper_id else 'check'
    return f'{where}-{what}-{task.time:%H%M}-{secrets.token_hex(2)}'


def schedule_page(request, task_form=None, give_form=None):
    ever, today = task_states()
    tasks = list(Task.objects.select_related('hopper'))
    for task in tasks:
        task.label = task_label(task)
        # a daily task starts again every day, a once task is done for good
        task.state = (today if task.daily else ever).get(task.task_id)
    occupied = [b.number for b in Bed.objects.all() if b.occupied]
    return render(request, 'ward/schedule.html', {
        'page': 'schedule',
        'trips': trips(tasks),
        'task_form': task_form or TaskForm(),
        'give_form': give_form or GiveNowForm(),
        'hoppers': Hopper.objects.all(),
        'occupied': occupied,
    })


@nurse_required
def schedule(request):
    return schedule_page(request)


@nurse_required
@require_POST
def task_add(request):
    form = TaskForm(request.POST)
    if not form.is_valid():
        return schedule_page(request, task_form=form)
    task = form.save(commit=False)
    task.task_id = new_task_id(task)
    task.save()
    messages.success(request, f'Task added for {task.time:%H:%M}.')
    return redirect('schedule')


@nurse_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.delete()
    messages.success(request, f'Task at {task.time:%H:%M} removed.')
    return redirect('schedule')


@nurse_required
@require_POST
def give_now(request):
    form = GiveNowForm(request.POST)
    if form.is_valid() and not Bed.objects.get(number=form.cleaned_data['bed']).occupied:
        form.add_error('bed', 'This bed has no patient.')
    if not form.is_valid():
        return schedule_page(request, give_form=form)
    now = timezone.localtime().time().replace(second=0, microsecond=0)
    task = Task(bed=form.cleaned_data['bed'], time=now, daily=False,
                hopper=form.cleaned_data['hopper'], count=form.cleaned_data['count'])
    task.task_id = new_task_id(task)
    task.save()
    messages.success(request, f'The robot takes {task.count} x {task.hopper.medicine} '
                              f'to bed {task.bed} on its next trip.')
    return redirect('schedule')


@nurse_required
@require_POST
def hoppers(request):
    for hopper in Hopper.objects.all():
        name = request.POST.get(f'hopper_{hopper.number}', '').strip()[:100]
        if name != hopper.medicine:
            hopper.medicine = name
            hopper.save()
    messages.success(request, 'Hopper names saved.')
    return redirect('schedule')


# patient records and the visits log, for doctors and nurses

def chart(visits, field, unit, decimals, low, high):
    """A small line chart of one reading as SVG coordinates, the normal range shaded."""
    points = [(v.time, getattr(v, field)) for v in visits if getattr(v, field) is not None]
    width, height, pad = 600, 150, 14
    if not points:
        return {'empty': True, 'unit': unit}
    values = [value for _, value in points]
    top = max(values + [high]) + (high - low) * 0.15
    bottom = min(values + [low]) - (high - low) * 0.15

    def y(value):
        return round(pad + (top - value) / (top - bottom) * (height - 2 * pad), 1)

    step = (width - 2 * pad) / max(len(points) - 1, 1)
    dots = [{'x': round(pad + i * step, 1), 'y': y(value), 'value': value, 'time': time,
             'out': not low <= value <= high} for i, (time, value) in enumerate(points)]
    return {
        'empty': False, 'unit': unit, 'decimals': decimals, 'width': width, 'height': height,
        'line': ' '.join(f"{d['x']},{d['y']}" for d in dots), 'dots': dots,
        'band_top': y(high), 'band_height': round(y(low) - y(high), 1),
        'low': low, 'high': high, 'last': dots[-1],
    }


@staff_required
def patients(request):
    current = [{'patient': b.patient, 'bed': b, 'vitals': latest_vitals(b.patient)}
               for b in room_beds() if b.patient]
    past = Patient.objects.filter(discharged__isnull=False).order_by('-discharged')[:20]
    return render(request, 'ward/patients.html', {
        'page': 'patients', 'current': current, 'past': past})


@staff_required
def patient(request, pk):
    person = get_object_or_404(Patient, pk=pk)
    visits = list(Visit.objects.filter(patient=person).order_by('time'))
    charts = [dict(chart(visits[-30:], field, unit, decimals, low, high), label=label)
              for field, label, unit, decimals, low, high in VITALS]
    return render(request, 'ward/patient.html', {
        'page': 'patients', 'person': person, 'charts': charts,
        'visits': list(reversed(visits)), 'vitals': latest_vitals(person)})


@staff_required
def visits(request):
    """One day of visits, grouped by trip. Tasks the robot could not do have no trip."""
    # days with visits, in ward local time
    days = [d.date() for d in Visit.objects.datetimes('time', 'day', order='DESC')]
    try:
        day = datetime.strptime(request.GET.get('day', ''), '%Y-%m-%d').date()
    except ValueError:
        day = days[0] if days else timezone.localdate()

    rows = Visit.objects.filter(time__date=day).select_related('patient').order_by('time')
    bed = request.GET.get('bed', '')
    if bed.isdigit():
        rows = rows.filter(bed=int(bed))
    problems = request.GET.get('problems') == '1'
    if problems:
        rows = rows.exclude(status='done')

    trips = []
    for visit in rows:
        if not trips or trips[-1]['trip'] != visit.trip:
            trips.append({'trip': visit.trip, 'start': visit.time, 'visits': []})
        trips[-1]['visits'].append(visit)

    older = [d for d in days if d < day]
    newer = [d for d in days if d > day]
    return render(request, 'ward/visits.html', {
        'page': 'visits', 'day': day, 'trips': trips, 'bed': bed, 'problems': problems,
        'older': older[0] if older else None, 'newer': newer[-1] if newer else None,
        'beds': range(1, 9), 'count': rows.count(),
    })


# video call with the robot's display

@staff_required
def call(request):
    return render(request, 'ward/call.html', {
        'page': 'call', 'robot_ws': settings.ROBOT_WS,
        'caller': request.user.get_full_name() or request.user.username})
