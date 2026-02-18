from django import forms
from core.models import Interest
from .models import Event, EventRegistration


class EventFilterForm(forms.Form):
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    city = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    interests = forms.ModelChoiceField(
        queryset=Interest.objects.all(),
        required=False,
        label='Интерес',
        empty_label='--- Всички ---'
    )

    kid_friendly = forms.ChoiceField(
        required=False,
        choices=[
            ('', '--- Всички ---'),
            ('yes', 'Да'),
            ('no', 'Не')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cities = Event.objects.values_list('city', flat=True).distinct()
        self.fields['city'].choices = [('', '--- Всички ---')] + [(city, city) for city in cities]


class EventRegistrationForm(forms.ModelForm):
    class Meta:
        model = EventRegistration
        fields = ['full_name', 'child_name', 'child_age']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Три имена'}),
            'child_name': forms.TextInput(attrs={'placeholder': 'Две имена на детето'}),
            'child_age': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Възраст'}),
        }
