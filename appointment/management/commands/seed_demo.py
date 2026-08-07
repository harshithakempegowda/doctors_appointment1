import datetime
import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from appointment.models import Doctor, Patient, Appointment, Review


DOCTORS = [
    ("Ananya Rao", "cardiology", "MBBS, MD (Cardiology)", 12, 800,
     "Specialist in heart health with over a decade of experience treating hypertension and arrhythmia."),
    ("Rohan Mehta", "general", "MBBS", 6, 400,
     "General physician focused on preventive care and everyday health concerns."),
    ("Priya Nair", "dermatology", "MBBS, MD (Dermatology)", 9, 600,
     "Dermatologist specializing in acne, skin allergies, and cosmetic dermatology."),
    ("Karthik Iyer", "orthopedics", "MBBS, MS (Ortho)", 15, 900,
     "Orthopedic surgeon with expertise in joint replacement and sports injuries."),
    ("Sneha Kulkarni", "pediatrics", "MBBS, MD (Pediatrics)", 8, 500,
     "Pediatrician passionate about child health, vaccination and nutrition."),
    ("Arjun Verma", "psychiatry", "MBBS, MD (Psychiatry)", 10, 700,
     "Psychiatrist helping patients manage anxiety, depression and stress-related conditions."),
]

PATIENTS = [
    ("Meera Shah", 29, "F", "9876500001"),
    ("Vikram Singh", 41, "M", "9876500002"),
    ("Divya Menon", 34, "F", "9876500003"),
]


class Command(BaseCommand):
    help = "Seed the database with demo doctors, patients, and sample appointments."

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@medicare.local', 'admin12345')
            self.stdout.write(self.style.SUCCESS("Created superuser 'admin' / 'admin12345'"))

        created_doctors = []
        for name, spec, qual, exp, fee, bio in DOCTORS:
            username = name.lower().replace(' ', '.')
            if User.objects.filter(username=username).exists():
                continue
            user = User.objects.create_user(username=username, password='doctor12345',
                                             email=f"{username}@medicare.local")
            doctor = Doctor.objects.create(
                user=user, name=name, specialization=spec, qualification=qual,
                experience_years=exp, consultation_fee=fee, profile=bio,
                available_days='mon,tue,wed,thu,fri',
            )
            created_doctors.append(doctor)

        created_patients = []
        for name, age, gender, phone in PATIENTS:
            username = name.lower().replace(' ', '.')
            if User.objects.filter(username=username).exists():
                continue
            user = User.objects.create_user(username=username, password='patient12345',
                                             email=f"{username}@example.com")
            patient = Patient.objects.create(user=user, name=name, age=age, gender=gender, phone=phone)
            created_patients.append(patient)

        doctors = list(Doctor.objects.all())
        patients = list(Patient.objects.all())
        today = datetime.date.today()

        if doctors and patients:
            for i in range(8):
                doctor = random.choice(doctors)
                patient = random.choice(patients)
                date = today + datetime.timedelta(days=random.randint(-10, 15))
                time = datetime.time(hour=random.choice([9, 10, 11, 14, 15, 16]))
                status = random.choice(['pending', 'confirmed', 'completed', 'completed'])
                if Appointment.objects.filter(doctor=doctor, date=date, time=time).exists():
                    continue
                appt = Appointment.objects.create(
                    doctor=doctor, patient=patient, date=date, time=time,
                    reason="Routine check-up and consultation.",
                    status=status,
                )
                if status == 'completed' and random.random() > 0.4:
                    Review.objects.get_or_create(
                        appointment=appt, doctor=doctor, patient=patient,
                        defaults={'rating': random.randint(3, 5), 'comment': 'Great consultation, very helpful.'}
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Doctors: {Doctor.objects.count()}, Patients: {Patient.objects.count()}, "
            f"Appointments: {Appointment.objects.count()}"
        ))
        self.stdout.write("Doctor logins: <name.with.dot> / doctor12345  |  Patient logins: <name.with.dot> / patient12345")
