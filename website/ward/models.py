"""Ward data. Bed, Task and Visit follow the scobo_interfaces messages."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Bed(models.Model):
    number = models.PositiveSmallIntegerField(
        primary_key=True, validators=[MinValueValidator(1), MaxValueValidator(8)])

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'Bed {self.number}'

    @property
    def patient(self):
        return self.patients.filter(discharged__isnull=True).first()

    @property
    def occupied(self):
        return self.patient is not None


class Patient(models.Model):
    SEX = [('F', 'Female'), ('M', 'Male'), ('O', 'Other')]

    name = models.CharField(max_length=100)
    age = models.PositiveSmallIntegerField()
    sex = models.CharField(max_length=1, choices=SEX)
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name='patients')
    notes = models.TextField(blank=True)
    admitted = models.DateField()
    # empty while the patient is on the ward
    discharged = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['bed', 'name']
        constraints = [
            models.UniqueConstraint(fields=['bed'], condition=models.Q(discharged__isnull=True),
                                    name='one_patient_per_bed'),
        ]

    def __str__(self):
        return self.name

    @property
    def initials(self):
        return ''.join(part[0] for part in self.name.split()[:2]).upper()


class Hopper(models.Model):
    """One of the three pill hoppers. The name only helps the nurses."""
    number = models.PositiveSmallIntegerField(
        primary_key=True, validators=[MinValueValidator(1), MaxValueValidator(3)])
    medicine = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'Hopper {self.number}: {self.medicine or "empty"}'


class Task(models.Model):
    # task id sent to the robot, also used in its visit records
    task_id = models.SlugField(max_length=60, unique=True)
    # 0 means every occupied bed (a round)
    bed = models.PositiveSmallIntegerField(validators=[MaxValueValidator(8)])
    time = models.TimeField()
    daily = models.BooleanField(default=True)
    temperature = models.BooleanField(default=False)
    pulse_oximeter = models.BooleanField(default=False)
    hopper = models.ForeignKey(Hopper, on_delete=models.PROTECT, null=True, blank=True)
    count = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(5)])
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['time', 'bed']

    def __str__(self):
        return self.task_id


class Visit(models.Model):
    """A visit record from the robot, or a task it could not do."""
    # id of the row in the robot's ward.db, so a record sent twice is stored once
    robot_id = models.PositiveIntegerField(unique=True)
    time = models.DateTimeField()
    trip = models.CharField(max_length=20, blank=True)
    bed = models.PositiveSmallIntegerField()
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    tasks = models.CharField(max_length=300, blank=True)
    # empty when not measured
    temperature = models.FloatField(null=True, blank=True)
    heart_rate = models.FloatField(null=True, blank=True)
    spo2 = models.FloatField(null=True, blank=True)
    pills = models.PositiveSmallIntegerField(default=0)
    collected = models.BooleanField(default=False)
    status = models.CharField(max_length=200)

    class Meta:
        ordering = ['-time']

    def __str__(self):
        return f'{timezone.localtime(self.time):%Y-%m-%d %H:%M} bed {self.bed}: {self.status}'

    @property
    def ok(self):
        return self.status == 'done'
