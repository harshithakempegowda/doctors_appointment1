from django.db import IntegrityError, transaction
from rest_framework import viewsets, permissions, filters, mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, APIException
from rest_framework.response import Response

from . import services
from .models import Doctor, Appointment, Review
from .serializers import (
    DoctorSerializer, AppointmentSerializer, AppointmentStatusSerializer, ReviewSerializer,
)


class SlotConflict(APIException):
    """HTTP 409 — the slot was taken by a competing request."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This slot is already booked with the doctor."
    default_code = "slot_unavailable"


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


class AppointmentViewSet(mixins.CreateModelMixin,
                         mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    """
    Authenticated endpoint — /api/appointments/

    * Patients list/retrieve/create only their own appointments.
    * Doctors list/retrieve only appointments booked with them.
    * POST /api/appointments/                 book a slot (patients only)
    * POST /api/appointments/<id>/cancel/     cancel (patients: >= 2 h before start)
    * PATCH /api/appointments/<id>/status/    update status / notes (doctors only)

    Double bookings are rejected with HTTP 409 (or 400 when the clash is caught
    by validation first).
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

    def create(self, request, *args, **kwargs):
        if not hasattr(request.user, 'patient_profile'):
            raise PermissionDenied("Only patients can book appointments.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            appointment = services.book_slot(
                doctor=data['doctor'],
                patient=request.user.patient_profile,
                date=data['date'],
                time=data['time'],
                reason=data['reason'],
            )
        except services.SlotUnavailable as exc:
            raise SlotConflict(str(exc))
        return Response(self.get_serializer(appointment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        by_patient = hasattr(request.user, 'patient_profile')
        try:
            services.cancel_appointment(appointment, by_patient=by_patient)
        except services.CancellationNotAllowed as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(appointment).data)

    @action(detail=True, methods=['patch'], url_path='status')
    def set_status(self, request, pk=None):
        if not hasattr(request.user, 'doctor_profile'):
            raise PermissionDenied("Only doctors can update appointment status.")
        appointment = self.get_object()
        serializer = AppointmentStatusSerializer(appointment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise SlotConflict("Another active appointment already holds this slot.")
        return Response(self.get_serializer(appointment).data)
