#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Survey, Student
from django.contrib.auth.models import User

# List all surveys
print("=== ALL SURVEYS ===")
for survey in Survey.objects.all():
    print(f"ID: {survey.id}, Title: {survey.title}, Status: {survey.status}, School: {survey.school.name if survey.school else 'None'}")

print("\n=== ALL STUDENTS ===")
for student in Student.objects.all():
    print(f"ID: {student.id}, User: {student.user.username}, School: {student.school.name if student.school else 'None'}")

print("\n=== TESTING QUERY ===")
# Try to simulate the query
if Student.objects.exists():
    first_student = Student.objects.first()
    print(f"Testing with student: {first_student.user.username}, School: {first_student.school}")
    if first_student.school:
        surveys = Survey.objects.filter(school=first_student.school, status='active')
        print(f"Found {surveys.count()} active surveys for this school")
        for survey in surveys:
            print(f"  - {survey.title}")
