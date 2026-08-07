from django.contrib import admin
from .models import Doctor, Patient, Appointment, Review


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialization', 'experience_years', 'consultation_fee', 'is_active')
    list_filter = ('specialization', 'is_active')
    search_fields = ('name', 'profile')


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'age', 'gender', 'phone')
    search_fields = ('name',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('date', 'time', 'doctor', 'patient', 'status')
    list_filter = ('status', 'date', 'doctor')
    search_fields = ('doctor__name', 'patient__name')
    date_hierarchy = 'date'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'patient', 'rating', 'created_at')
    list_filter = ('rating',)
