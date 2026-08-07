from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings

from .models import Doctor, Patient, Appointment, Review
from .forms import (
    PatientSignUpForm, DoctorSignUpForm, DoctorProfileForm,
    AppointmentBookingForm, AppointmentStatusForm, ReviewForm, DoctorSearchForm,
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _is_doctor(user):
    return hasattr(user, 'doctor_profile')


def _is_patient(user):
    return hasattr(user, 'patient_profile')


def _notify(subject, message, to_email):
    """Best-effort email notification (prints to console in dev)."""
    if not to_email:
        return
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=True)
    except Exception:
        pass


# ---------------------------------------------------------
# Public pages
# ---------------------------------------------------------

def home(request):
    top_doctors = Doctor.objects.filter(is_active=True).order_by('-experience_years')[:6]
    return render(request, 'appointment/home.html', {'top_doctors': top_doctors})


def doctor_list(request):
    form = DoctorSearchForm(request.GET or None)
    doctors = Doctor.objects.filter(is_active=True)

    if form.is_valid():
        q = form.cleaned_data.get('q')
        specialization = form.cleaned_data.get('specialization')
        if q:
            doctors = doctors.filter(Q(name__icontains=q) | Q(profile__icontains=q))
        if specialization:
            doctors = doctors.filter(specialization=specialization)

    paginator = Paginator(doctors, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'appointment/doctor_list.html', {
        'page_obj': page_obj,
        'form': form,
    })


def doctor_profile(request, doctor_id):
    doctor = get_object_or_404(Doctor, pk=doctor_id, is_active=True)
    reviews = doctor.reviews.select_related('patient').all()[:10]
    return render(request, 'appointment/doctor_profile.html', {
        'doctor': doctor,
        'reviews': reviews,
    })


# ---------------------------------------------------------
# Auth
# ---------------------------------------------------------

def signup_choice(request):
    return render(request, 'registration/signup_choice.html')


def patient_signup(request):
    if request.method == 'POST':
        form = PatientSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to MediCare! Your patient account is ready.")
            return redirect('post_login_redirect')
    else:
        form = PatientSignUpForm()
    return render(request, 'registration/signup.html', {'form': form, 'role': 'Patient'})


def doctor_signup(request):
    if request.method == 'POST':
        form = DoctorSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your doctor profile has been created.")
            return redirect('post_login_redirect')
    else:
        form = DoctorSignUpForm()
    return render(request, 'registration/signup.html', {'form': form, 'role': 'Doctor'})


@login_required
def post_login_redirect(request):
    if _is_doctor(request.user):
        return redirect('doctor_dashboard')
    if _is_patient(request.user):
        return redirect('patient_dashboard')
    return redirect('home')


# ---------------------------------------------------------
# Patient area
# ---------------------------------------------------------

@login_required
def patient_dashboard(request):
    if not _is_patient(request.user):
        messages.error(request, "That page is only available to patients.")
        return redirect('home')

    patient = request.user.patient_profile
    appointments = patient.appointments.select_related('doctor').all()

    status_filter = request.GET.get('status')
    if status_filter:
        appointments = appointments.filter(status=status_filter)

    stats = {
        'total': patient.appointments.count(),
        'upcoming': patient.appointments.filter(status__in=['pending', 'confirmed']).count(),
        'completed': patient.appointments.filter(status='completed').count(),
        'cancelled': patient.appointments.filter(status='cancelled').count(),
    }

    return render(request, 'appointment/patient_dashboard.html', {
        'appointments': appointments,
        'stats': stats,
    })


@login_required
def book_appointment(request, doctor_id):
    if not _is_patient(request.user):
        messages.error(request, "Only patients can book appointments.")
        return redirect('home')

    doctor = get_object_or_404(Doctor, pk=doctor_id, is_active=True)

    if request.method == 'POST':
        form = AppointmentBookingForm(request.POST, doctor=doctor)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.doctor = doctor
            appointment.patient = request.user.patient_profile
            appointment.save()

            _notify(
                "New appointment request",
                f"{appointment.patient.name} requested an appointment on "
                f"{appointment.date} at {appointment.time}.",
                doctor.user.email,
            )
            messages.success(request, "Appointment requested! You'll be notified once the doctor confirms it.")
            return redirect('patient_dashboard')
    else:
        form = AppointmentBookingForm(doctor=doctor)

    return render(request, 'appointment/book_appointment.html', {
        'form': form,
        'doctor': doctor,
    })


@login_required
def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)

    is_owner_patient = _is_patient(request.user) and appointment.patient.user == request.user
    is_owner_doctor = _is_doctor(request.user) and appointment.doctor.user == request.user
    if not (is_owner_patient or is_owner_doctor):
        messages.error(request, "You don't have permission to cancel this appointment.")
        return redirect('home')

    if request.method == 'POST':
        appointment.status = 'cancelled'
        appointment.save()
        messages.info(request, "Appointment cancelled.")
        return redirect('patient_dashboard' if is_owner_patient else 'doctor_dashboard')

    return render(request, 'appointment/confirm_cancel.html', {'appointment': appointment})


@login_required
def leave_review(request, appointment_id):
    appointment = get_object_or_404(
        Appointment, pk=appointment_id, status='completed'
    )
    if not (_is_patient(request.user) and appointment.patient.user == request.user):
        messages.error(request, "You can't review this appointment.")
        return redirect('patient_dashboard')

    if hasattr(appointment, 'review'):
        messages.info(request, "You've already reviewed this appointment.")
        return redirect('patient_dashboard')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.appointment = appointment
            review.doctor = appointment.doctor
            review.patient = appointment.patient
            review.save()
            messages.success(request, "Thanks for your feedback!")
            return redirect('patient_dashboard')
    else:
        form = ReviewForm()

    return render(request, 'appointment/leave_review.html', {
        'form': form,
        'appointment': appointment,
    })


# ---------------------------------------------------------
# Doctor area
# ---------------------------------------------------------

@login_required
def doctor_dashboard(request):
    if not _is_doctor(request.user):
        messages.error(request, "That page is only available to doctors.")
        return redirect('home')

    doctor = request.user.doctor_profile
    appointments = doctor.appointments.select_related('patient').all()

    status_filter = request.GET.get('status')
    if status_filter:
        appointments = appointments.filter(status=status_filter)

    stats = {
        'total': doctor.appointments.count(),
        'pending': doctor.appointments.filter(status='pending').count(),
        'confirmed': doctor.appointments.filter(status='confirmed').count(),
        'completed': doctor.appointments.filter(status='completed').count(),
    }

    return render(request, 'appointment/doctor_dashboard.html', {
        'appointments': appointments,
        'stats': stats,
        'doctor': doctor,
    })


@login_required
def update_appointment_status(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    if not (_is_doctor(request.user) and appointment.doctor.user == request.user):
        messages.error(request, "You don't have permission to update this appointment.")
        return redirect('home')

    if request.method == 'POST':
        form = AppointmentStatusForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            _notify(
                f"Your appointment is now {appointment.get_status_display()}",
                f"Dr. {appointment.doctor.name} updated your appointment on "
                f"{appointment.date} at {appointment.time} to '{appointment.get_status_display()}'.",
                appointment.patient.user.email,
            )
            messages.success(request, "Appointment updated.")
            return redirect('doctor_dashboard')
    else:
        form = AppointmentStatusForm(instance=appointment)

    return render(request, 'appointment/update_status.html', {
        'form': form,
        'appointment': appointment,
    })


@login_required
def edit_doctor_profile(request):
    if not _is_doctor(request.user):
        messages.error(request, "That page is only available to doctors.")
        return redirect('home')

    doctor = request.user.doctor_profile
    if request.method == 'POST':
        form = DoctorProfileForm(request.POST, request.FILES, instance=doctor)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect('doctor_dashboard')
    else:
        form = DoctorProfileForm(instance=doctor)

    return render(request, 'appointment/edit_doctor_profile.html', {'form': form})


@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)

    is_owner_patient = _is_patient(request.user) and appointment.patient.user == request.user
    is_owner_doctor = _is_doctor(request.user) and appointment.doctor.user == request.user
    if not (is_owner_patient or is_owner_doctor or request.user.is_superuser):
        messages.error(request, "You don't have permission to view this appointment.")
        return redirect('home')

    return render(request, 'appointment/appointment_detail.html', {'appointment': appointment})
