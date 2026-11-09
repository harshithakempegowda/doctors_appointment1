import datetime

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg


SPECIALIZATIONS = [
    ('general', 'General Physician'),
    ('cardiology', 'Cardiologist'),
    ('dermatology', 'Dermatologist'),
    ('neurology', 'Neurologist'),
    ('orthopedics', 'Orthopedic Surgeon'),
    ('pediatrics', 'Pediatrician'),
    ('psychiatry', 'Psychiatrist'),
    ('dentistry', 'Dentist'),
    ('ent', 'ENT Specialist'),
    ('gynecology', 'Gynecologist'),
]

DAYS_OF_WEEK = [
    ('mon', 'Monday'), ('tue', 'Tuesday'), ('wed', 'Wednesday'),
    ('thu', 'Thursday'), ('fri', 'Friday'), ('sat', 'Saturday'), ('sun', 'Sunday'),
]


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=30, choices=SPECIALIZATIONS, default='general')
    profile = models.TextField(help_text="Short bio shown on the doctor's public profile")
    qualification = models.CharField(max_length=150, blank=True, help_text="e.g. MBBS, MD (Cardiology)")
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=500)
    available_days = models.CharField(
        max_length=50, blank=True,
        help_text="Comma separated day codes, e.g. mon,tue,wed"
    )
    available_from = models.TimeField(default='09:00')
    available_to = models.TimeField(default='17:00')
    photo = models.ImageField(upload_to='doctor_photos/', blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text="Inactive doctors are hidden from search")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"Dr. {self.name} ({self.get_specialization_display()})"

    @property
    def average_rating(self):
        return self.reviews.aggregate(avg=Avg('rating'))['avg'] or 0

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def available_day_list(self):
        return [d.strip() for d in self.available_days.split(',') if d.strip()]


class Patient(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    name = models.CharField(max_length=100)
    age = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(120)])
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='O')
    phone = models.CharField(max_length=15, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


ACTIVE_STATUSES = ('pending', 'confirmed')


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    time = models.TimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    doctor_notes = models.TextField(blank=True, help_text="Doctor's remarks after the visit")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']
        # A doctor cannot have two active appointments in the same slot
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'date', 'time'],
                condition=models.Q(status__in=['pending', 'confirmed']),
                name='unique_active_slot_per_doctor'
            )
        ]

    def __str__(self):
        return f"{self.date} {self.time} - {self.doctor.name} - {self.patient.name}"

    @property
    def is_upcoming(self):
        return self.date >= timezone.localdate() and self.status in ACTIVE_STATUSES

    @property
    def starts_at(self):
        """Appointment start as a timezone-aware datetime."""
        naive = datetime.datetime.combine(self.date, self.time)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def cancellation_deadline(self):
        """Last moment a patient may still cancel."""
        hours = getattr(settings, 'CANCELLATION_CUTOFF_HOURS', 2)
        return self.starts_at - datetime.timedelta(hours=hours)

    @property
    def patient_can_cancel(self):
        return self.status in ACTIVE_STATUSES and timezone.now() <= self.cancellation_deadline


class Review(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='reviews')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reviews')
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating}★ for {self.doctor.name} by {self.patient.name}"
