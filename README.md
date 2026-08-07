<<<<<<< HEAD
# MediCare — Doctor Appointment Booking System

A full-stack appointment booking platform built with **Django**, **Django REST Framework**, and **Bootstrap 5**. Patients can search for doctors, book appointments, and leave reviews; doctors can manage their profile and respond to appointment requests. A read-only REST API is also exposed for doctors, appointments, and reviews.

## ✨ Features

- **Role-based accounts** — separate signup flows and dashboards for Patients and Doctors
- **Doctor discovery** — search by name/keyword and filter by specialization, with pagination
- **Appointment booking** with server-side validation that prevents double-booking the same doctor slot
- **Appointment lifecycle** — Pending → Confirmed → Completed → Cancelled, managed from the doctor's dashboard
- **Reviews & ratings** — patients can rate a doctor after a completed visit; average rating shown on the doctor's profile
- **Email notifications** (console backend in dev) sent to the doctor on new bookings and to the patient on status changes
- **Doctor profile management** — bio, qualifications, fees, availability, and photo upload
- **REST API** (Django REST Framework) — `/api/doctors/`, `/api/appointments/`, `/api/reviews/` with search, ordering, and pagination
- **Django Admin** for full CRUD over all models
- **Seed command** (`seed_demo`) to populate demo doctors, patients, and appointments in one shot

## 🧱 Tech Stack

- Backend: Python, Django, Django REST Framework
- Database: SQLite (swap `DATABASES` in `config/settings.py` for Postgres/MySQL in production)
- Frontend: Django Templates, Bootstrap 5, Bootstrap Icons
- Auth: Django's built-in auth system, extended with `Doctor`/`Patient` profile models

## 🗂 Project Structure

```
medicare/
├── config/                # Project settings, root urls
├── appointment/
│   ├── models.py          # Doctor, Patient, Appointment, Review
│   ├── forms.py            # Signup, booking, review, search forms
│   ├── views.py             # All page views
│   ├── api.py               # DRF viewsets
│   ├── serializers.py       # DRF serializers
│   ├── admin.py
│   ├── templates/
│   ├── static/
│   └── management/commands/seed_demo.py
├── requirements.txt
└── manage.py
```

## 🚀 Getting Started

```bash
# 1. Clone and enter the project
cd medicare

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. (Optional) Load demo data — doctors, patients, sample appointments
python manage.py seed_demo

# 6. Run the dev server
python manage.py runserver
```

Visit **http://127.0.0.1:8000/**.

### Demo credentials (after running `seed_demo`)

| Role    | Username example  | Password       |
|---------|--------------------|-----------------|
| Admin   | `admin`             | `admin12345`    |
| Doctor  | `ananya.rao`        | `doctor12345`   |
| Patient | `meera.shah`        | `patient12345`  |

(All seeded doctor usernames are `firstname.lastname`, e.g. `rohan.mehta`, `priya.nair`.)

## 🔌 API Endpoints

| Endpoint                | Method | Description                              |
|--------------------------|--------|-------------------------------------------|
| `/api/doctors/`           | GET    | List/search doctors (`?search=`, `?ordering=`) |
| `/api/doctors/<id>/`      | GET    | Doctor detail                             |
| `/api/appointments/`      | GET/POST | List or create appointments (auth required, scoped to the logged-in user) |
| `/api/reviews/`           | GET    | List reviews                              |

## 🩺 Possible Next Steps

- Time-slot based availability instead of free-text date/time
- Payment integration for consultation fees
- Real email/SMS notifications via a provider (e.g. SendGrid, Twilio)
- Video-consultation link generation for telemedicine appointments
- Unit tests for booking-conflict logic and role-based permissions

## 🐳 Running with Docker

```bash
# Build and start the container (serves on http://localhost:8000)
docker compose up --build

# Run in the background
docker compose up --build -d

# Create a superuser inside the running container
docker compose exec web python manage.py createsuperuser

# Load demo data inside the running container
docker compose exec web python manage.py seed_demo
```

The container runs migrations and `collectstatic` automatically on startup
(see `docker-entrypoint.sh`). The SQLite database, uploaded media, and
collected static files are persisted in named Docker volumes
(`sqlite_data`, `media_data`, `static_data`) so they survive container
restarts. To seed demo data automatically on first boot instead, set
`SEED_DEMO: "True"` under `environment:` in `docker-compose.yml`.

Set a real `DJANGO_SECRET_KEY` and keep `DJANGO_DEBUG` set to `"False"`
before deploying anywhere besides your own machine.

## 📄 License

Built as a personal/academic portfolio project. Free to reuse and adapt.
=======
# doctors_appointment
>>>>>>> 8db07c58eb811bc43ce47a5082fe0223f50cd3d6
