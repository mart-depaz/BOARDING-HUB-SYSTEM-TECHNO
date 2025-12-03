from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('admin-panel-portal/', views.admin_login, name='admin_login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('database/', views.database_view, name='database'),
    path('audits/', views.property_audits, name='audits'),
    path('students/', views.boarding_students, name='students'),
    path('students/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('emergency/', views.emergency_log, name='emergency'),
    path('provisioning/', views.provisioning_hub, name='provisioning_hub'),
    path('provisioning/add-property/', views.add_property_owner, name='add_property_owner'),
    path('provisioning/add-student/', views.add_student, name='add_student'),
    path('manage/departments/', views.manage_departments, name='manage_departments'),
    path('manage/programs/', views.manage_programs, name='manage_programs'),
    path('profile/', views.admin_profile, name='admin_profile'),
    # Survey Management
    path('surveys/', views.survey_list, name='survey_list'),
    path('surveys/create/', views.survey_create, name='survey_create'),
    path('surveys/<int:survey_id>/', views.survey_detail, name='survey_detail'),
    path('surveys/<int:survey_id>/responses/', views.survey_responses, name='survey_responses'),
    path('surveys/responses/<int:response_id>/', views.survey_response_detail, name='survey_response_detail'),
    path('surveys/responses/<int:response_id>/register/', views.register_from_survey, name='register_from_survey'),
    path('surveys/responses/<int:response_id>/delete/', views.delete_survey_response, name='delete_survey_response'),
    path('surveys/responses/<int:response_id>/restore/', views.restore_survey_response, name='restore_survey_response'),
    path('surveys/responses/<int:response_id>/permanent-delete/', views.permanently_delete_survey_response, name='permanently_delete_survey_response'),
    path('surveys/<int:survey_id>/delete/', views.delete_survey, name='delete_survey'),
    path('students/<int:student_id>/delete/', views.delete_student, name='delete_student'),
]

