#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Survey, Student, School

print("=== ALL SURVEYS IN DATABASE ===")
for survey in Survey.objects.all().order_by('-id'):
    print(f"ID: {survey.id}, Title: {survey.title}, Status: {survey.status}, School: {survey.school.name if survey.school else 'None'}, Recipient: {survey.recipient_type if hasattr(survey, 'recipient_type') else 'N/A'}")

print("\n=== STUDENTS AND THEIR SCHOOLS ===")
for student in Student.objects.all():
    print(f"Student: {student.user.username}, School: {student.school.name if student.school else 'None'}")

print("\n=== TESTING QUERY FOR FIRST STUDENT ===")
if Student.objects.exists():
    student = Student.objects.first()
    print(f"Testing with student: {student.user.username}")
    print(f"Student's school: {student.school.name if student.school else 'None'}")
    
    if student.school:
        print(f"\nActive surveys for students (status='active', recipient in ['students', 'both']):")
        surveys = Survey.objects.filter(
            school=student.school,
            status='active',
            recipient_type__in=['students', 'both']
        ).order_by('-created_at')
        print(f"Found {surveys.count()} surveys:")
        for s in surveys:
            print(f"  - ID: {s.id}, Title: {s.title}, Status: {s.status}, Recipient: {s.recipient_type}")
        
        print(f"\nAll surveys for this school (regardless of status):")
        all_surveys = Survey.objects.filter(school=student.school).order_by('-id')
        print(f"Found {all_surveys.count()} total surveys:")
        for s in all_surveys:
            print(f"  - ID: {s.id}, Title: {s.title}, Status: {s.status}, Recipient: {s.recipient_type}")
