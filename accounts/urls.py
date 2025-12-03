from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', RedirectView.as_view(url='login/', permanent=False), name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-register/', views.admin_registration, name='admin_register'),
    path('student-signup/', views.student_signup, name='student_signup'),
    path('property-owner-signup/', views.property_owner_signup, name='property_owner_signup'),
    path('redirect/', views.redirect_after_login, name='redirect_after_login'),
    path('forgot-password/request/', views.password_reset_request, name='password_reset_request'),
    path('forgot-password/verify/', views.password_reset_verify, name='password_reset_verify'),
    path('forgot-password/reset/', views.password_reset_complete, name='password_reset_complete'),
]

