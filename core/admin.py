from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    School, UserProfile, Property, Student, 
    BoardingAssignment, MaintenanceRequest, 
    PropertyReview, EmergencyLog, Department, Program,
    Survey, SurveySection, SurveyQuestion, SurveyResponse, SurveyAnswer
)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'email_domain', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'email_domain']
    readonly_fields = ['created_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'school', 'created_at']
    list_filter = ['role', 'school', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'school']


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['property_id', 'owner', 'school', 'address', 'status', 'safety_rating', 'capacity', 'current_occupancy']
    list_filter = ['status', 'school', 'has_wifi', 'has_kitchen', 'verified_at']
    search_fields = ['property_id', 'address', 'owner__username', 'owner__email']
    readonly_fields = ['created_at', 'updated_at', 'verified_at']
    raw_id_fields = ['owner', 'school', 'verified_by']
    fieldsets = (
        ('Basic Information', {
            'fields': ('property_id', 'owner', 'school', 'name', 'description')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'zip_code', 'latitude', 'longitude')
        }),
        ('Property Details', {
            'fields': ('capacity', 'current_occupancy', 'monthly_rent')
        }),
        ('Amenities', {
            'fields': ('has_wifi', 'has_kitchen', 'has_laundry', 'has_parking', 'has_security')
        }),
        ('Verification', {
            'fields': ('status', 'safety_rating', 'verified_at', 'verified_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'school', 'is_active', 'created_at']
    list_filter = ['school', 'is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['school']


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'department', 'is_active', 'created_at']
    list_filter = ['department', 'is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['department']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'user', 'school', 'department', 'program', 'date_of_birth', 'created_at']
    list_filter = ['school', 'department', 'program', 'created_at']
    search_fields = ['student_id', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'school', 'department', 'program']


@admin.register(BoardingAssignment)
class BoardingAssignmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'property', 'status', 'start_date', 'end_date', 'agreement_signed']
    list_filter = ['status', 'agreement_signed', 'start_date', 'created_at']
    search_fields = ['student__student_id', 'student__user__username', 'property__property_id']
    readonly_fields = ['created_at', 'updated_at', 'agreement_signed_at']
    raw_id_fields = ['student', 'property']


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'student', 'property', 'priority', 'status', 'created_at']
    list_filter = ['priority', 'status', 'created_at']
    search_fields = ['title', 'description', 'student__student_id', 'property__property_id']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    raw_id_fields = ['student', 'property']


@admin.register(PropertyReview)
class PropertyReviewAdmin(admin.ModelAdmin):
    list_display = ['property', 'student', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['property__property_id', 'student__student_id', 'comment']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['property', 'student']


@admin.register(EmergencyLog)
class EmergencyLogAdmin(admin.ModelAdmin):
    list_display = ['incident_id', 'incident_type', 'property', 'severity', 'status', 'created_at']
    list_filter = ['severity', 'status', 'incident_type', 'created_at']
    search_fields = ['incident_id', 'incident_type', 'description', 'property__property_id']
    readonly_fields = ['created_at', 'resolved_at']
    raw_id_fields = ['property', 'student', 'reported_by']


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ['title', 'school', 'status', 'category', 'created_by', 'created_at']
    list_filter = ['status', 'school', 'category', 'created_at']
    search_fields = ['title', 'description', 'category', 'unique_code']
    readonly_fields = ['unique_code', 'created_at', 'updated_at']
    raw_id_fields = ['school', 'created_by']


@admin.register(SurveySection)
class SurveySectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'survey', 'order', 'created_at']
    list_filter = ['survey', 'created_at']
    search_fields = ['title', 'survey__title']
    raw_id_fields = ['survey']


@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'section', 'question_type', 'is_required', 'order']
    list_filter = ['question_type', 'is_required', 'section__survey']
    search_fields = ['text', 'section__title']
    raw_id_fields = ['section']


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'student_email', 'survey', 'status', 'created_at', 'reviewed_by']
    list_filter = ['status', 'survey', 'created_at', 'reviewed_at']
    search_fields = ['student_name', 'student_email', 'provided_student_id', 'survey__title']
    readonly_fields = ['created_at', 'updated_at', 'reviewed_at']
    raw_id_fields = ['survey', 'reviewed_by', 'student']


@admin.register(SurveyAnswer)
class SurveyAnswerAdmin(admin.ModelAdmin):
    list_display = ['response', 'question', 'answer_text', 'answer_choice', 'answer_rating', 'answer_date']
    list_filter = ['question__question_type', 'created_at']
    search_fields = ['answer_text', 'answer_choice', 'response__student_name']
    raw_id_fields = ['response', 'question']


# Customize Django Admin Site
admin.site.site_header = "Boarding Hub - Django Administration"
admin.site.site_title = "Boarding Hub Admin"
admin.site.index_title = "Welcome to Boarding Hub Administration"
