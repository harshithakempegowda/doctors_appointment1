"""
Live concurrency test: N patients try to book the SAME doctor slot at the same
instant through the REST API, and we check that exactly one booking is created.

Usage (the server must already be running):

    python manage.py runserver                      # terminal 1
    python manage.py concurrency_test               # terminal 2

    # with Docker:
    docker compose up -d
    docker compose exec web python manage.py concurrency_test --base-url http://localhost:8000

What it does
------------
1. Creates one test doctor and N test patients (loadtest.*), if missing.
2. Logs every patient in (sequentially) and keeps their session cookie.
3. Releases N threads together with a barrier so all POSTs hit the server at once.
4. Counts HTTP status codes and then checks the database for duplicate bookings.
5. Deletes the test appointments (use --keep to leave them for inspection).

Only the Python standard library is used for the HTTP client.
"""
import collections
import datetime
import http.cookiejar
import json
import threading
import time as time_module
import urllib.error
import urllib.parse
import urllib.request

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from appointment.models import ACTIVE_STATUSES, Appointment, Doctor, Patient

PASSWORD = 'loadtest12345'


class Client:
    """Tiny session-aware HTTP client (cookies + CSRF header)."""

    def __init__(self, base_url):
        self.base = base_url.rstrip('/')
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self):
        for cookie in self.jar:
            if cookie.name == 'csrftoken':
                return cookie.value
        return ''

    def request(self, method, path, data=None, json_body=None):
        headers = {'Referer': self.base + '/'}
        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode()
            headers['Content-Type'] = 'application/json'
        elif data is not None:
            body = urllib.parse.urlencode(data).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if method != 'GET':
            headers['X-CSRFToken'] = self._csrf()
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=60) as resp:
                return resp.status, resp.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode('utf-8', 'replace')

    def login(self, username, password):
        self.request('GET', '/login/')  # sets the csrftoken cookie
        status, _ = self.request('POST', '/login/',
                                 data={'username': username, 'password': password})
        return status


class Command(BaseCommand):
    help = "Fire N simultaneous API bookings for one slot and verify no duplicates are created."

    def add_arguments(self, parser):
        parser.add_argument('--requests', type=int, default=30, help='Number of concurrent requests (default 30)')
        parser.add_argument('--base-url', default='http://127.0.0.1:8000', help='Running server URL')
        parser.add_argument('--keep', action='store_true', help='Keep test appointments afterwards')

    def handle(self, *args, **opts):
        n = opts['requests']
        base_url = opts['base_url']

        doctor = self._ensure_doctor()
        patients = self._ensure_patients(n)

        slot_date = timezone.localdate() + datetime.timedelta(days=3)
        slot_time = datetime.time(10, 0)
        Appointment.objects.filter(doctor=doctor, date=slot_date, time=slot_time).delete()

        self.stdout.write(f"Logging in {n} test patients at {base_url} ...")
        clients = []
        for patient in patients:
            client = Client(base_url)
            try:
                status = client.login(patient.user.username, PASSWORD)
            except urllib.error.URLError as exc:
                raise CommandError(
                    f"Cannot reach the server at {base_url} ({exc.reason}). "
                    "Start it first, e.g. 'python manage.py runserver' or 'docker compose up -d'.")
            if status not in (200, 302) or not any(c.name == 'sessionid' for c in client.jar):
                raise CommandError(
                    f"Login failed for {patient.user.username} (HTTP {status}). "
                    f"Is the server running at {base_url} and using the same database?")
            clients.append(client)

        payload = {'doctor': doctor.pk, 'date': slot_date.isoformat(),
                   'time': slot_time.strftime('%H:%M:%S'), 'reason': 'concurrency test'}

        self.stdout.write(f"Firing {n} simultaneous booking requests for doctor #{doctor.pk} "
                          f"on {slot_date} at {slot_time:%H:%M} ...")
        barrier = threading.Barrier(n)
        results = [None] * n

        def worker(i):
            barrier.wait()
            started = time_module.perf_counter()
            try:
                status, _ = clients[i].request('POST', '/api/appointments/', json_body=payload)
            except Exception as exc:  # network error etc.
                status = f'error:{type(exc).__name__}'
            results[i] = (status, time_module.perf_counter() - started)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        wall_start = time_module.perf_counter()
        for t in threads: t.start()
        for t in threads: t.join()
        wall = time_module.perf_counter() - wall_start

        counts = collections.Counter(r[0] for r in results)
        active = Appointment.objects.filter(
            doctor=doctor, date=slot_date, time=slot_time, status__in=ACTIVE_STATUSES).count()
        total_rows = Appointment.objects.filter(doctor=doctor, date=slot_date, time=slot_time).count()

        self.stdout.write("")
        self.stdout.write("HTTP status codes returned:")
        meaning = {201: 'created (booking succeeded)', 400: 'rejected by validation',
                   409: 'rejected (slot conflict)'}
        for code, count in sorted(counts.items(), key=lambda kv: str(kv[0])):
            self.stdout.write(f"  {code}: {count:>3}  {meaning.get(code, '')}")
        self.stdout.write("")
        self.stdout.write(f"Total wall time          : {wall:.2f} s")
        self.stdout.write(f"Bookings created (201)   : {counts.get(201, 0)}")
        self.stdout.write(f"Active rows in database  : {active}")
        self.stdout.write(f"All rows for that slot   : {total_rows}")
        duplicates = max(active - 1, 0)
        server_errors = sum(c for code, c in counts.items()
                            if isinstance(code, str) or (isinstance(code, int) and code >= 500))

        if not opts['keep']:
            Appointment.objects.filter(doctor=doctor, date=slot_date, time=slot_time).delete()

        self.stdout.write("")
        if duplicates == 0 and counts.get(201, 0) == 1 and server_errors == 0:
            self.stdout.write(self.style.SUCCESS(
                f"PASS: {n} concurrent requests -> exactly 1 booking, 0 duplicate bookings, 0 server errors."))
        elif duplicates == 0:
            self.stdout.write(self.style.WARNING(
                f"0 duplicate bookings, but {server_errors} request(s) failed with a server/network error "
                f"and {counts.get(201, 0)} succeeded. Check the server log."))
        else:
            raise CommandError(f"FAIL: {duplicates} duplicate active booking(s) found!")

    # -- setup helpers ---------------------------------------------------
    def _ensure_doctor(self):
        user, created = User.objects.get_or_create(
            username='loadtest.doctor', defaults={'email': 'loadtest.doctor@example.com'})
        if created:
            user.set_password(PASSWORD)
            user.save()
        doctor, _ = Doctor.objects.get_or_create(
            user=user, defaults={'name': 'Load Test Doctor', 'profile': 'Created by concurrency_test'})
        return doctor

    def _ensure_patients(self, n):
        patients = []
        for i in range(n):
            username = f'loadtest.patient{i:02d}'
            user, created = User.objects.get_or_create(
                username=username, defaults={'email': f'{username}@example.com'})
            if created:
                user.set_password(PASSWORD)
                user.save()
            patient, _ = Patient.objects.get_or_create(
                user=user, defaults={'name': username, 'age': 30})
            patients.append(patient)
        return patients
