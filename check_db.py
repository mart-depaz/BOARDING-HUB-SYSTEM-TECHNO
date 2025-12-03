#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Survey, Student, School
from django.contrib.auth.models import User

print("=" * 100)
print("SURVEY INVESTIGATION - ADMIN VS STUDENT VIEW")
print("=" * 100)

# Find the admin user
admin_users = User.objects.filter(profile__role='school_admin')
print(f"\n1. ADMIN USERS:")
print("-" * 100)
for admin in admin_users:
    print(f"  Username: {admin.username}")
    print(f"  School: {admin.profile.school.name if admin.profile.school else 'None'}")
    
    # Show surveys created by this admin
    surveys_created = Survey.objects.filter(created_by=admin)
    print(f"  Surveys created by this admin: {surveys_created.count()}")
    for survey in surveys_created:
        print(f"    - ID {survey.id}: {survey.title} (Status: {survey.status}, School: {survey.school.name if survey.school else 'None'})")

print(f"\n2. ALL SURVEYS IN DATABASE:")
print("-" * 100)
all_surveys = Survey.objects.all().order_by('-id')
for survey in all_surveys:
    created_by = survey.created_by.username if survey.created_by else "Unknown"
    print(f"  ID {survey.id}: {survey.title}")
    print(f"    Status: {survey.status}")
    print(f"    School: {survey.school.name if survey.school else 'None'}")
    print(f"    Recipient: {survey.recipient_type if hasattr(survey, 'recipient_type') else 'N/A'}")
    print(f"    Created by: {created_by}")
    print()

print(f"3. STUDENTS AND THEIR SCHOOLS:")
print("-" * 100)
for student in Student.objects.all():
    print(f"  Student: {student.user.username}")
    print(f"  School: {student.school.name if student.school else 'None'}")
    
    # Show what surveys this student would see
    if student.school:
        surveys = Survey.objects.filter(
            school=student.school,
            status='active',
            recipient_type__in=['students', 'both']
        )
        print(f"  Active surveys for this student's school: {surveys.count()}")
        for survey in surveys:
            print(f"    - ID {survey.id}: {survey.title} (Created by: {survey.created_by.username if survey.created_by else 'Unknown'})")
    print()

print(f"4. SCHOOL ANALYSIS:")
print("-" * 100)
for school in School.objects.all():
    print(f"\nSchool: {school.name}")
    print(f"  Surveys in this school: {Survey.objects.filter(school=school).count()}")
    
    # Show all surveys for this school
    surveys = Survey.objects.filter(school=school).order_by('-id')
    for survey in surveys:
        print(f"    - ID {survey.id}: {survey.title} (Status: {survey.status}, Recipient: {survey.recipient_type})")
    
    # Show admins for this school
    admins = User.objects.filter(profile__role='school_admin', profile__school=school)
    print(f"  Admins for this school: {admins.count()}")
    for admin in admins:
        print(f"    - {admin.username}")

print("\n" + "=" * 100)
