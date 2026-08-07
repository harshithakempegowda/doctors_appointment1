from rest_framework import viewsets, permissions, filters
from rest_framework.exceptions import PermissionDenied

from .models import Doctor, Appointment, Review
from .serializers import DoctorSerializer, AppointmentSerializer, ReviewSerializer


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """Public, read-only endpoint for browsing doctors — /api/doctors/"""
    queryset = Doctor.objects.filter(is_active=True)
    serializer_class = DoctorSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'specialization', 'profile']
    ordering_fields = ['experience_years', 'consultation_fee', 'name']


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Public, read-only endpoint for browsing reviews — /api/reviews/"""
    queryset = Review.objects.select_related('doctor', 'patient').all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    Authenticated endpoint — /api/appointments/
    Patients see & create only their own appointments.
    Doctors see only appointments booked with them (read-only here;
    status changes go through the web dashboard).
    """
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'patient_profile'):
            return Appointment.objects.filter(patient=user.patient_profile)
        if hasattr(user, 'doctor_profile'):
            return Appointment.objects.filter(doctor=user.doctor_profile)
        return Appointment.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'patient_profile'):
            raise PermissionDenied("Only patients can book appointments.")
        serializer.save(patient=user.patient_profile)
