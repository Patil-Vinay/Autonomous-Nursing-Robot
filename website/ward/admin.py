from django.contrib import admin

from ward.models import Bed, Hopper, Patient, Task, Visit


class PatientInline(admin.TabularInline):
    model = Patient
    extra = 0
    fields = ['name', 'age', 'sex', 'admitted', 'discharged']


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'patient']
    inlines = [PatientInline]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['name', 'bed', 'age', 'admitted', 'discharged']
    list_filter = ['discharged']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'bed', 'time', 'daily', 'temperature', 'pulse_oximeter', 'hopper', 'count']


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['time', 'bed', 'patient', 'temperature', 'heart_rate', 'spo2', 'status']
    list_filter = ['bed', 'status']


admin.site.register(Hopper)

# admin page titles
admin.site.site_header = 'SCOBO Admin Panel'
admin.site.site_title = 'SCOBO Admin Panel'
admin.site.index_title = 'Ward data'
