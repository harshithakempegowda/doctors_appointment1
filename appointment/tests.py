"""
Unit tests for the booking-conflict logic, the 2-hour cancellation cutoff,
role-based permissions and the REST API.

Run with:  python manage.py test
"""
import datetime
import threading
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import Appointment, Doctor, Patient


# ---------------------------------------------------------------- helpers

def make_doctor(username='dr.test'):
    user = User.objects.create_user(username, password='pw12345!', email=f'{username}@x.com')
    return Doctor.objects.create(user=user, name=username, profile='bio')


def make_patient(username='pat.test'):
    user = User.objects.create_user(username, password='pw12345!', email=f'{username}@x.com')
    return Patient.objects.create(user=user, name=username, age=30)


def future_slot(days=3, hour=10):
    day = timezone.localdate() + datetime.timedelta(days=days)
    return day, datetime.time(hour, 0)


# ---------------------------------------------------------------- model constraint

class SlotConstraintTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.p1 = make_patient('p1')
        self.p2 = make_patient('p2')
        self.date, self.time = future_slot()

    def _create(self, patient, status='pending'):
        return Appointment.objects.create(
            doctor=self.doctor, patient=patient, date=self.date,
            time=self.time, reason='checkup', status=status)

    def test_database_rejects_second_active_booking_for_same_slot(self):
        self._create(self.p1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._create(self.p2)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_slot_can_be_rebooked_after_cancellation(self):
        self._create(self.p1, status='cancelled')
        self._create(self.p2)  # must not raise
        self.assertEqual(Appointment.objects.filter(status='pending').count(), 1)

    def test_different_doctors_can_share_a_time(self):
        other = make_doctor('dr.other')
        self._create(self.p1)
        Appointment.objects.create(doctor=other, patient=self.p2, date=self.date,
                                   time=self.time, reason='x')
        self.assertEqual(Appointment.objects.count(), 2)


# ---------------------------------------------------------------- services

class BookSlotServiceTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.p1 = make_patient('p1')
        self.p2 = make_patient('p2')
        self.date, self.time = future_slot()

    def test_books_a_free_slot(self):
        appt = services.book_slot(doctor=self.doctor, patient=self.p1,
                                  date=self.date, time=self.time, reason='r')
        self.assertEqual(appt.status, 'pending')

    def test_second_booking_for_same_slot_is_rejected(self):
        services.book_slot(doctor=self.doctor, patient=self.p1,
                           date=self.date, time=self.time, reason='r')
        with self.assertRaises(services.SlotUnavailable):
            services.book_slot(doctor=self.doctor, patient=self.p2,
                               date=self.date, time=self.time, reason='r')
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_in_the_past_is_rejected(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        with self.assertRaises(services.SlotUnavailable):
            services.book_slot(doctor=self.doctor, patient=self.p1,
                               date=yesterday, time=self.time, reason='r')

    def test_integrity_error_is_converted_to_slot_unavailable(self):
        """Simulates losing the race: the pre-check passes, the DB constraint fires."""
        services.book_slot(doctor=self.doctor, patient=self.p1,
                           date=self.date, time=self.time, reason='r')
        with mock.patch('appointment.services.Appointment.objects.filter') as fake_filter:
            fake_filter.return_value.exists.return_value = False  # pre-check says "free"
            with self.assertRaises(services.SlotUnavailable):
                services.book_slot(doctor=self.doctor, patient=self.p2,
                                   date=self.date, time=self.time, reason='r')
        self.assertEqual(Appointment.objects.count(), 1)


class CancellationRuleTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = make_patient()
        self.date, self.time = future_slot(days=1, hour=12)
        self.appt = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient, date=self.date,
            time=self.time, reason='r', status='confirmed')

    def _at(self, hours_before):
        return self.appt.starts_at - datetime.timedelta(hours=hours_before)

    def test_patient_can_cancel_well_before_cutoff(self):
        with mock.patch('django.utils.timezone.now', return_value=self._at(5)):
            services.cancel_appointment(self.appt, by_patient=True)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, 'cancelled')

    def test_patient_can_cancel_exactly_at_cutoff(self):
        with mock.patch('django.utils.timezone.now', return_value=self._at(2)):
            services.cancel_appointment(self.appt, by_patient=True)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, 'cancelled')

    def test_patient_cannot_cancel_inside_two_hour_window(self):
        with mock.patch('django.utils.timezone.now', return_value=self._at(1.9)):
            with self.assertRaises(services.CancellationNotAllowed):
                services.cancel_appointment(self.appt, by_patient=True)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, 'confirmed')

    def test_doctor_can_cancel_inside_window(self):
        with mock.patch('django.utils.timezone.now', return_value=self._at(0.5)):
            services.cancel_appointment(self.appt, by_patient=False)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, 'cancelled')

    def test_cannot_cancel_a_completed_appointment(self):
        self.appt.status = 'completed'
        self.appt.save()
        with self.assertRaises(services.CancellationNotAllowed):
            services.cancel_appointment(self.appt, by_patient=False)

    def test_cannot_cancel_twice(self):
        services.cancel_appointment(self.appt, by_patient=False)
        with self.assertRaises(services.CancellationNotAllowed):
            services.cancel_appointment(self.appt, by_patient=False)


# ---------------------------------------------------------------- web views

class BookingViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.p1 = make_patient('p1')
        self.p2 = make_patient('p2')
        self.date, self.time = future_slot()
        self.url = reverse('book_appointment', args=[self.doctor.pk])
        self.payload = {'date': self.date.isoformat(), 'time': '10:00', 'reason': 'headache'}

    def test_patient_can_book(self):
        self.client.login(username='p1', password='pw12345!')
        resp = self.client.post(self.url, self.payload)
        self.assertRedirects(resp, reverse('patient_dashboard'))
        self.assertEqual(Appointment.objects.count(), 1)

    def test_second_patient_gets_error_not_a_duplicate(self):
        self.client.login(username='p1', password='pw12345!')
        self.client.post(self.url, self.payload)
        self.client.logout()
        self.client.login(username='p2', password='pw12345!')
        resp = self.client.post(self.url, self.payload)
        self.assertEqual(resp.status_code, 200)  # form re-rendered with an error
        self.assertContains(resp, 'already booked')
        self.assertEqual(Appointment.objects.count(), 1)

    def test_doctor_cannot_book(self):
        self.client.login(username='dr.test', password='pw12345!')
        resp = self.client.post(self.url, self.payload)
        self.assertRedirects(resp, reverse('home'))
        self.assertEqual(Appointment.objects.count(), 0)

    def test_anonymous_user_is_redirected_to_login(self):
        resp = self.client.post(self.url, self.payload)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])


class CancelViewPermissionTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.owner = make_patient('owner')
        self.other = make_patient('other')
        date, time = future_slot(days=5)
        self.appt = Appointment.objects.create(
            doctor=self.doctor, patient=self.owner, date=date, time=time, reason='r')

    def test_other_patient_cannot_cancel(self):
        self.client.login(username='other', password='pw12345!')
        self.client.post(reverse('cancel_appointment', args=[self.appt.pk]))
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, 'pending')

    def test_owner_can_cancel(self):
        self.client.login(username='owner', password='pw12345!')
        self.client.post(reverse('cancel_appointment', args=[self.appt.pk]))
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, 'cancelled')


# ---------------------------------------------------------------- REST API

class AppointmentApiTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.p1 = make_patient('p1')
        self.p2 = make_patient('p2')
        self.date, self.time = future_slot()
        self.payload = {'doctor': self.doctor.pk, 'date': self.date.isoformat(),
                        'time': '10:00:00', 'reason': 'fever'}

    def _client(self, username):
        c = APIClient()
        c.login(username=username, password='pw12345!')
        return c

    def test_doctors_endpoint_is_public(self):
        self.assertEqual(APIClient().get('/api/doctors/').status_code, 200)

    def test_anonymous_cannot_book(self):
        self.assertIn(APIClient().post('/api/appointments/', self.payload, format='json').status_code,
                      (401, 403))

    def test_patient_can_book_without_sending_patient_id(self):
        resp = self._client('p1').post('/api/appointments/', self.payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Appointment.objects.get().patient, self.p1)

    def test_duplicate_booking_is_rejected(self):
        self._client('p1').post('/api/appointments/', self.payload, format='json')
        resp = self._client('p2').post('/api/appointments/', self.payload, format='json')
        self.assertIn(resp.status_code, (400, 409))
        self.assertEqual(Appointment.objects.count(), 1)

    def test_doctor_cannot_book_via_api(self):
        resp = self._client('dr.test').post('/api/appointments/', self.payload, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_patient_cannot_modify_status_by_put_or_delete(self):
        self._client('p1').post('/api/appointments/', self.payload, format='json')
        appt = Appointment.objects.get()
        c = self._client('p1')
        self.assertEqual(c.delete(f'/api/appointments/{appt.pk}/').status_code, 405)
        self.assertEqual(c.put(f'/api/appointments/{appt.pk}/', self.payload, format='json').status_code, 405)

    def test_api_cancel_respects_two_hour_cutoff(self):
        appt = Appointment.objects.create(doctor=self.doctor, patient=self.p1,
                                          date=self.date, time=self.time, reason='r')
        c = self._client('p1')
        with mock.patch('django.utils.timezone.now',
                        return_value=appt.starts_at - datetime.timedelta(hours=1)):
            resp = c.post(f'/api/appointments/{appt.pk}/cancel/')
        self.assertEqual(resp.status_code, 400)
        resp = c.post(f'/api/appointments/{appt.pk}/cancel/')  # days ahead: allowed
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'cancelled')

    def test_doctor_can_update_status_but_patient_cannot(self):
        appt = Appointment.objects.create(doctor=self.doctor, patient=self.p1,
                                          date=self.date, time=self.time, reason='r')
        url = f'/api/appointments/{appt.pk}/status/'
        self.assertEqual(self._client('p1').patch(url, {'status': 'confirmed'}, format='json').status_code, 403)
        resp = self._client('dr.test').patch(url, {'status': 'confirmed'}, format='json')
        self.assertEqual(resp.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'confirmed')


# ---------------------------------------------------------------- concurrency

class ConcurrentBookingTests(TransactionTestCase):
    """Fires several simultaneous bookings for one slot; exactly one may win."""

    def test_only_one_of_many_simultaneous_bookings_succeeds(self):
        doctor = make_doctor()
        patients = [make_patient(f'c{i}') for i in range(8)]
        date, time = future_slot()
        barrier = threading.Barrier(len(patients))
        results = []

        def attempt(patient):
            try:
                barrier.wait()
                services.book_slot(doctor=doctor, patient=patient, date=date, time=time, reason='r')
                results.append('ok')
            except services.SlotUnavailable:
                results.append('rejected')
            except Exception as exc:  # any other failure is a test failure
                results.append(f'error:{type(exc).__name__}')
            finally:
                connection.close()

        threads = [threading.Thread(target=attempt, args=(p,)) for p in patients]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(results.count('ok'), 1, results)
        self.assertEqual(Appointment.objects.filter(doctor=doctor, date=date, time=time).count(), 1)
