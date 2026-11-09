"""
Booking and cancellation business rules, shared by the web views and the REST API.

Why this module exists
----------------------
Two patients can press "Book" for the same doctor slot at the same moment.
A form-level "is the slot free?" check alone is not enough, because both
requests can pass it before either one saves (a classic check-then-insert race).

Protection is therefore layered:

1. ``UniqueConstraint(doctor, date, time)`` on active appointments (see models.py)
   makes the *database* reject a second active booking for the same slot.
2. ``book_slot`` runs the check and the insert inside ``transaction.atomic()``
   and converts the database's ``IntegrityError`` into a clean ``SlotUnavailable``
   error, so users get a clear message instead of a server error.
3. SQLite is configured with ``transaction_mode = IMMEDIATE`` (settings.py) so
   concurrent writers queue up instead of failing with "database is locked".
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, ACTIVE_STATUSES


class SlotUnavailable(Exception):
    """The requested doctor slot is already taken (or not bookable)."""


class CancellationNotAllowed(Exception):
    """The appointment cannot be cancelled by this user right now."""


def slot_is_in_past(date, time):
    """True if the given date/time has already started."""
    probe = Appointment(date=date, time=time)
    return probe.starts_at <= timezone.now()


def book_slot(*, doctor, patient, date, time, reason):
    """Create an appointment atomically, or raise SlotUnavailable."""
    if slot_is_in_past(date, time):
        raise SlotUnavailable("You can't book an appointment in the past.")

    try:
        with transaction.atomic():
            taken = Appointment.objects.filter(
                doctor=doctor, date=date, time=time, status__in=ACTIVE_STATUSES
            ).exists()
            if taken:
                raise SlotUnavailable(
                    "This slot is already booked with the doctor. Please choose another time."
                )
            return Appointment.objects.create(
                doctor=doctor, patient=patient, date=date, time=time, reason=reason
            )
    except IntegrityError as exc:
        # Another request won the race; the database constraint rejected ours.
        raise SlotUnavailable(
            "This slot was just booked by someone else. Please choose another time."
        ) from exc


def check_cancellable(appointment, *, by_patient):
    """Raise CancellationNotAllowed if the appointment can't be cancelled."""
    if appointment.status not in ACTIVE_STATUSES:
        raise CancellationNotAllowed(
            f"This appointment is already {appointment.get_status_display().lower()}."
        )
    if by_patient and not appointment.patient_can_cancel:
        hours = getattr(settings, 'CANCELLATION_CUTOFF_HOURS', 2)
        raise CancellationNotAllowed(
            f"Appointments can only be cancelled at least {hours} hours before the start time. "
            "Please contact the doctor directly."
        )


def cancel_appointment(appointment, *, by_patient):
    """Cancel an appointment, enforcing the cutoff for patients."""
    with transaction.atomic():
        # Re-read inside the transaction so we judge the latest state.
        current = Appointment.objects.get(pk=appointment.pk)
        check_cancellable(current, by_patient=by_patient)
        current.status = 'cancelled'
        current.save(update_fields=['status', 'updated_at'])
    appointment.status = 'cancelled'
    return appointment
