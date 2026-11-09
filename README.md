# MediCare — Doctor Appointment Booking System

A full-stack appointment booking platform built with **Django**, **Django REST Framework** and **Bootstrap 5**.
Patients search for doctors, book appointments and leave reviews; doctors manage their profile and
respond to appointment requests. A REST API exposes doctors, reviews and appointments.

> Academic project (Oct 2024 – Feb 2025). Runs locally; see [Limitations](#limitations).

## Team and my role

<!-- TODO: fill in with your real details before sharing this repo -->
- Team size: **3**
- My role: **Backend & DevOps** — booking logic, REST API, tests, Docker setup
- Teammates: frontend UI and patient profile views

## Features

- **Role-based accounts** — separate signup flows and dashboards for patients and doctors
- **Doctor discovery** — search by name/keyword, filter by specialization, pagination
- **Double-booking protection** — database constraint + atomic booking (see below)
- **2-hour cancellation cutoff** — patients can cancel only until 2 hours before the start time; doctors can always cancel
- **Appointment lifecycle** — Pending → Confirmed → Completed → Cancelled
- **Reviews & ratings** after a completed visit
- **Email notifications** (console backend in development)
- **REST API** — doctors, reviews, appointments (book / cancel / update status)
- **Django Admin**, demo-data seed command, Docker setup

## How double bookings are prevented

Two patients can press "Book" for the same slot at the same moment, so a form check alone is not enough
(both requests can pass it before either saves). Protection is layered:

1. **Database constraint** — `UniqueConstraint(doctor, date, time)` that applies to *active* (pending/confirmed)
   appointments only, so a cancelled slot can be rebooked (`appointment/models.py`).
2. **Atomic booking service** — `services.book_slot()` runs the check and insert inside `transaction.atomic()` and turns the
   database's `IntegrityError` into a clear `SlotUnavailable` message instead of a server error (`appointment/services.py`).
3. **SQLite write locking** — `transaction_mode: IMMEDIATE` and a 20 s timeout (`config/settings.py`) so simultaneous writers queue
   instead of failing with "database is locked".

The web form and the REST API share the same service, so both paths behave identically.

## Tech stack

Python 3.12, Django 5.1+, Django REST Framework, SQLite, Bootstrap 5, Docker / Docker Compose, gunicorn.

## Getting started (local)

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # optional demo data
python manage.py runserver
```

Open http://127.0.0.1:8000/

### Demo credentials (after `seed_demo`)

| Role    | Username       | Password       |
|---------|----------------|----------------|
| Admin   | `admin`        | `admin12345`   |
| Doctor  | `ananya.rao`   | `doctor12345`  |
| Patient | `meera.shah`   | `patient12345` |

## Running with Docker

```bash
docker compose up --build            # serves on http://localhost:8000
docker compose up --build -d         # in the background
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py createsuperuser
```

Migrations and `collectstatic` run automatically on start (`docker-entrypoint.sh`). The SQLite database, media files
and static files live in named volumes (`sqlite_data`, `media_data`, `static_data`) and survive restarts.
Set a real `DJANGO_SECRET_KEY` before deploying anywhere other than your own machine.

## Tests

### Unit and API tests

```bash
python manage.py test
```

28 tests cover: the slot constraint, the booking service (including losing a race), the cancellation rule
(well before, exactly at, and inside the 2-hour window), role-based permissions in the web views and the API,
and a threaded test where 8 simultaneous bookings for one slot must produce exactly one winner.

### Live concurrency test (30 simultaneous API requests)

Start the app with a multi-worker server, then fire 30 simultaneous booking requests for the same slot:

```bash
# terminal 1 — gunicorn, like the Docker image uses
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3

# terminal 2
python manage.py concurrency_test --requests 30 --base-url http://127.0.0.1:8000
```

With Docker:

```bash
docker compose up -d
docker compose exec web python manage.py concurrency_test --base-url http://localhost:8000
```

The command logs in 30 test patients, releases all requests together, prints the HTTP status codes
(`201` created, `400`/`409` rejected) and then checks the database for duplicate bookings.
Expected result: **exactly 1 booking, 0 duplicates**. Use gunicorn rather than `runserver` for this test —
Django's development server only queues 5 pending connections, so some of the 30 simultaneous connections can be reset
by the server before they reach the app (this does not affect the database result).

## API

| Endpoint                                | Method | Description                                               |
|-----------------------------------------|--------|-----------------------------------------------------------|
| `/api/doctors/`, `/api/doctors/<id>/`   | GET    | List / search doctors (`?search=`, `?ordering=`)          |
| `/api/reviews/`                         | GET    | List reviews                                              |
| `/api/appointments/`                    | GET    | Your appointments (patients: own; doctors: booked with them) |
| `/api/appointments/`                    | POST   | Book a slot (patients only). `409`/`400` if already booked |
| `/api/appointments/<id>/cancel/`        | POST   | Cancel (patients: at least 2 h before start)              |
| `/api/appointments/<id>/status/`        | PATCH  | Update status / notes (doctors only)                      |

## Project structure

```
config/                     settings, root urls
appointment/
├── models.py               Doctor, Patient, Appointment (+ slot constraint), Review
├── services.py             book_slot(), cancel_appointment() — shared business rules
├── views.py, forms.py      web UI
├── api.py, serializers.py  REST API
├── tests.py                unit, API and concurrency tests
└── management/commands/    seed_demo.py, concurrency_test.py
Dockerfile, docker-compose.yml, docker-entrypoint.sh
```

## Limitations

- **SQLite** uses file-level locking, so sustained heavy write traffic will slow down or fail. For production, switch
  `DATABASES` to **PostgreSQL**, which handles concurrent writes with row-level locking; the unique constraint and
  `transaction.atomic()` logic work unchanged.
- Availability is a free date/time field, not a generated list of time slots.
- Emails use the console backend; payments and video consultations are not implemented.

## License

Personal/academic portfolio project. Free to reuse and adapt.
