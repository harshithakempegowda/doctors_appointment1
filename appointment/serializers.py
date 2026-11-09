from rest_framework import serializers
from .models import Doctor, Appointment, Review, ACTIVE_STATUSES
from .services import slot_is_in_past


class DoctorSerializer(serializers.ModelSerializer):
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'specialization', 'specialization_display', 'qualification',
            'experience_years', 'consultation_fee', 'profile', 'average_rating',
            'review_count', 'available_days', 'available_from', 'available_to',
        ]


class ReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'doctor', 'patient_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['patient_name', 'created_at']


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'doctor', 'doctor_name', 'patient', 'patient_name',
            'date', 'time', 'reason', 'status', 'status_display',
            'doctor_notes', 'created_at',
        ]
        read_only_fields = ['patient', 'status', 'doctor_notes', 'created_at']

    def validate(self, attrs):
        doctor = attrs.get('doctor') or getattr(self.instance, 'doctor', None)
        date = attrs.get('date') or getattr(self.instance, 'date', None)
        time = attrs.get('time') or getattr(self.instance, 'time', None)

        if doctor is not None and not doctor.is_active:
            raise serializers.ValidationError("This doctor is not accepting appointments.")
        if date and time and slot_is_in_past(date, time):
            raise serializers.ValidationError("You can't book an appointment in the past.")

        clash = Appointment.objects.filter(
            doctor=doctor, date=date, time=time, status__in=ACTIVE_STATUSES
        )
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("This slot is already booked with the doctor.")
        return attrs


class AppointmentStatusSerializer(serializers.ModelSerializer):
    """Used by doctors to confirm / complete / cancel an appointment."""

    class Meta:
        model = Appointment
        fields = ['status', 'doctor_notes']
