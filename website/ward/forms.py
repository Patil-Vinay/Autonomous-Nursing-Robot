from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from ward.models import Hopper, Patient, Task

BED_CHOICES = [(n, f'Bed {n}') for n in range(1, 9)]


class AdmitForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['name', 'age', 'sex', 'admitted', 'notes']
        widgets = {
            'admitted': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['admitted'].initial = timezone.localdate()
        self.fields['age'].widget.attrs.update(min=0, max=120)


class TaskForm(forms.ModelForm):
    bed = forms.TypedChoiceField(choices=[(0, 'All occupied beds')] + BED_CHOICES, coerce=int)
    daily = forms.TypedChoiceField(choices=[(1, 'Every day'), (0, 'Once, today')],
                                   coerce=lambda v: v == '1', initial=1)

    class Meta:
        model = Task
        fields = ['bed', 'time', 'daily', 'temperature', 'pulse_oximeter', 'hopper', 'count']
        widgets = {
            'time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'count': forms.NumberInput(attrs={'min': 0, 'max': 5}),
        }
        labels = {'pulse_oximeter': 'Pulse oximeter', 'count': 'Pills'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hopper'].queryset = Hopper.objects.exclude(medicine='')
        self.fields['hopper'].empty_label = 'No medicine'
        self.fields['count'].required = False

    def clean(self):
        data = super().clean()
        hopper, count = data.get('hopper'), data.get('count') or 0
        data['count'] = count
        if hopper and not count:
            raise ValidationError('Give the number of pills.')
        if count and not hopper and 'hopper' not in self.errors:
            raise ValidationError('Pick the medicine for the pills.')
        if hopper and data.get('bed') == 0:
            raise ValidationError('Medicine is given to one bed at a time.')
        if not (data.get('temperature') or data.get('pulse_oximeter') or hopper):
            raise ValidationError('Pick at least one thing for the robot to do.')
        return data


class GiveNowForm(forms.Form):
    bed = forms.TypedChoiceField(choices=BED_CHOICES, coerce=int)
    hopper = forms.ModelChoiceField(queryset=Hopper.objects.exclude(medicine=''),
                                    empty_label=None)
    count = forms.IntegerField(min_value=1, max_value=5, initial=1)
