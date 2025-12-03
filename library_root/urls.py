"""
URL configuration for library_root project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from admin_panel.views import survey_take, setup_password

urlpatterns = [
    # Root URL - Always show student/owner login first
    path('', include('accounts.urls')),  # Authentication (login, logout, registration) - This is the default landing page
    # Public survey link (accessible without login)
    path('survey/<str:unique_code>/', survey_take, name='survey_take'),
    # Password setup (public - accessible via token)
    path('setup-password/<str:token>/', setup_password, name='setup_password'),
    # Student and Property Owner dashboards (protected)
    path('students/', include('students.urls')),  # Student dashboard
    path('properties/', include('properties.urls')),  # Property owner dashboard
    # Admin panel (protected - requires authentication and school_admin role)
    path('admin-panel/', include('admin_panel.urls')),  # School admin dashboard
    path('admin-panel-portal/', RedirectView.as_view(url='/admin-panel/admin-panel-portal/', permanent=False), name='admin_portal_redirect'),
    # Django admin (separate from school admin - only for superusers)
    path('admin/', admin.site.urls),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
