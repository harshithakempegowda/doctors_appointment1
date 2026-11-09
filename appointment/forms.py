from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Doctor, Patient, Appointment, Review, SPECIALIZATIONS, ACTIVE_STATUSES
from .services import slot_is_in_past


TEXT_INPUT = {'class': 'form-control'}


class PatientSignUpForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs=TEXT_INPUT))
    age = forms.IntegerField(min_value=0, max_value=120, widget=forms.NumberInput(attrs=TEXT_INPUT))
    gender = forms.ChoiceField(choices=Patient.GENDER_CHOICES, widget=forms.Select(attrs=TEXT_INPUT))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs=TEXT_INPUT))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('username', 'password1', 'password2'):
            self.fields[name].widget.attrs.update(TEXT_INPUT)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Patient.objects.create(
                user=user,
                name=user.username,
                age=self.cleaned_data['age'],
                gender=self.cleaned_data['gender'],
                phone=self.cleaned_data.get('phone', ''),
            )
        return user


class DoctorSignUpForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs=TEXT_INPUT))
    specialization = forms.ChoiceField(choices=SPECIALIZATIONS, widget=forms.Select(attrs=TEXT_INPUT))
    qualification = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs=TEXT_INPUT))
    experience_years = forms.IntegerField(min_value=0, initial=0, widget=forms.NumberInput(attrs=TEXT_INPUT))
    consultation_fee = forms.DecimalField(min_value=0, initial=500, widget=forms.NumberInput(attrs=TEXT_INPUT))
    profile = forms.CharField(widget=forms.Textarea(attrs={**TEXT_INPUT, 'rows': 4}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('username', 'password1', 'password2'):
            self.fields[name].widget.attrs.update(TEXT_INPUT)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Doctor.objects.create(
                user=user,
                name=user.username,
                specialization=self.cleaned_data['specialization'],
                qualification=self.cleaned_data.get('qualification', ''),
                experience_years=self.cleaned_data['experience_years'],
                consultation_fee=self.cleaned_data['consultation_fee'],
                profile=self.cleaned_data['profile'],
            )
        return user


class DoctorProfileForm(forms.ModelForm):
    class Meta:
        model = Doctor
        fields = [
            'name', 'specialization', 'qualification', 'experience_years',
            'consultation_fee', 'profile', 'available_days',
            'available_from', 'available_to', 'photo',
        ]
        widgets = {
            'name': forms.TextInput(attrs=TEXT_INPUT),
            'specialization': forms.Select(attrs=TEXT_INPUT),
            'qualification': forms.TextInput(attrs=TEXT_INPUT),
            'experience_years': forms.NumberInput(attrs=TEXT_INPUT),
            'consultation_fee': forms.NumberInput(attrs=TEXT_INPUT),
            'profile': forms.Textarea(attrs={**TEXT_INPUT, 'rows': 4}),
            'available_days': forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'mon,tue,wed,thu,fri'}),
            'available_from': forms.TimeInput(attrs=TEXT_INPUT, format='%H:%M'),
            'available_to': forms.TimeInput(attrs=TEXT_INPUT, format='%H:%M'),
        }


class AppointmentBookingForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['date', 'time', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={**TEXT_INPUT, 'type': 'date'}),
            'time': forms.TimeInput(attrs={**TEXT_INPUT, 'type': 'time'}),
            'reason': forms.Textarea(attrs={**TEXT_INPUT, 'rows': 3, 'placeholder': 'Briefly describe your symptoms or reason for visit'}),
        }

    def __init__(self, *args, doctor=None, **kwargs):
        self.doctor = doctor
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('date')
        time = cleaned.get('time')

        if date and time and slot_is_in_past(date, time):
            raise forms.ValidationError("You can't book an appointment in the past.")

        # Friendly early check. The real protection against simultaneous requests
        # is the database constraint + atomic booking in services.book_slot().
        if self.doctor and date and time:
            clash = Appointment.objects.filter(
                doctor=self.doctor, date=date, time=time,
                status__in=ACTIVE_STATUSES,
            )
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(
                    "This slot is already booked with the doctor. Please choose another time."
                )
        return cleaned


class AppointmentStatusForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['status', 'doctor_notes']
        widgets = {
            'status': forms.Select(attrs=TEXT_INPUT),
            'doctor_notes': forms.Textarea(attrs={**TEXT_INPUT, 'rows': 3}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} ★') for i in range(1, 6)], attrs=TEXT_INPUT),
            'comment': forms.Textarea(attrs={**TEXT_INPUT, 'rows': 3, 'placeholder': 'Share your experience (optional)'}),
        }


class DoctorSearchForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={
        **TEXT_INPUT, 'placeholder': 'Search by doctor name...'
    }))
    specialization = forms.ChoiceField(
        required=False,
        choices=[('', 'All Specializations')] + SPECIALIZATIONS,
        widget=forms.Select(attrs=TEXT_INPUT)
    )
