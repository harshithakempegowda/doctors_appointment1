from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from rest_framework.routers import DefaultRouter
from appointment.api import DoctorViewSet, AppointmentViewSet, ReviewViewSet

router = DefaultRouter()
router.register('doctors', DoctorViewSet, basename='api-doctor')
router.register('appointments', AppointmentViewSet, basename='api-appointment')
router.register('reviews', ReviewViewSet, basename='api-review')

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('appointment.urls')),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
