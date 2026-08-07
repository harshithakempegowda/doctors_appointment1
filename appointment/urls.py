from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Auth
    path('signup/', views.signup_choice, name='signup_choice'),
    path('signup/patient/', views.patient_signup, name='patient_signup'),
    path('signup/doctor/', views.doctor_signup, name='doctor_signup'),
    path('post-login/', views.post_login_redirect, name='post_login_redirect'),

    # Doctors (public)
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/<int:doctor_id>/', views.doctor_profile, name='doctor_profile'),

    # Patient area
    path('dashboard/patient/', views.patient_dashboard, name='patient_dashboard'),
    path('doctors/<int:doctor_id>/book/', views.book_appointment, name='book_appointment'),
    path('appointments/<int:appointment_id>/cancel/', views.cancel_appointment, name='cancel_appointment'),
    path('appointments/<int:appointment_id>/review/', views.leave_review, name='leave_review'),

    # Doctor area
    path('dashboard/doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('dashboard/doctor/profile/', views.edit_doctor_profile, name='edit_doctor_profile'),
    path('appointments/<int:appointment_id>/status/', views.update_appointment_status, name='update_appointment_status'),

    # Shared
    path('appointments/<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
]
