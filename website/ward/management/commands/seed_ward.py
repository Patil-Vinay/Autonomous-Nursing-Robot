"""Fills an empty database with the simulated ward: 8 beds, 3 hoppers, the patients
in beds 1-5, 7 and 8 and the plan of scobo_tasks/config/ward_plan.yaml.

python manage.py seed_ward
"""
from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ward.models import Bed, Hopper, Patient, Task

# patients for the sim, bed 6 is empty
PATIENTS = [
    (1, 'Suresh Joshi', 67, 'M', 8),
    (2, 'Meena Kulkarni', 54, 'F', 4),
    (3, 'Anil Deshmukh', 71, 'M', 6),
    (4, 'Kavita Rao', 45, 'F', 5),
    (5, 'Prakash Shinde', 62, 'M', 4),
    (7, 'Sunita Pawar', 58, 'F', 3),
    (8, 'Vijay Gaikwad', 49, 'M', 2),
]

HOPPERS = {1: 'Vitamin B12', 2: 'Paracetamol 500 mg', 3: ''}

# (id, bed, time, daily, temperature, pulse oximeter, hopper, count)
TASKS = [
    ('morning-round', 0, time(8, 0), True, True, True, None, 0),
    ('evening-round', 0, time(20, 0), True, True, True, None, 0),
    ('bed4-afternoon-pills', 4, time(15, 0), True, False, False, 2, 1),
    ('bed2-afternoon-pills', 2, time(15, 10), True, False, False, 1, 2),
    ('bed3-fever-check', 3, time(16, 0), False, True, False, None, 0),
]


class Command(BaseCommand):
    help = 'Adds the simulated ward to an empty database'

    def handle(self, *args, **options):
        for n in range(1, 9):
            Bed.objects.get_or_create(number=n)
        for n, medicine in HOPPERS.items():
            Hopper.objects.get_or_create(number=n, defaults={'medicine': medicine})

        if Patient.objects.exists() or Task.objects.exists():
            self.stdout.write('Patients or tasks already there, left as they are')
            return

        today = timezone.localdate()
        for bed, name, age, sex, days in PATIENTS:
            Patient.objects.create(name=name, age=age, sex=sex, bed_id=bed,
                                   admitted=today - timedelta(days=days))
        for task_id, bed, at, daily, temp, pulse, hopper, count in TASKS:
            Task.objects.create(task_id=task_id, bed=bed, time=at, daily=daily, temperature=temp,
                                pulse_oximeter=pulse, hopper_id=hopper, count=count)
        self.stdout.write(f'Added {len(PATIENTS)} patients and {len(TASKS)} tasks')
