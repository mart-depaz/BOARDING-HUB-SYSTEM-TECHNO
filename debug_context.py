#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Student, Survey
from django.contrib.auth.models import User

print("=== SIMULATING STUDENT DASHBOARD VIEW ===\n")

# Get first student user
student_user = User.objects.filter(student_profile__isnull=False).first()
if not student_user:
    print("No student users found!")
    exit(1)

print(f"Student user: {student_user.username}")
student = student_user.student_profile

print(f"Student's school: {student.school.name if student.school else 'None'}")

# This is what the view does:
surveys = []
pending_surveys = 0
try:
    if student.school:
        # Get active surveys from the student's school that are for students or both
        surveys = Survey.objects.filter(
            school=student.school,
            status='active',
            recipient_type__in=['students', 'both']  # Show surveys for students or both
        ).order_by('-created_at')
        pending_surveys = surveys.count()
        print(f"\n✅ Query executed successfully")
except Exception as e:
    print(f"\n❌ Error: {e}")
    surveys = []
    pending_surveys = 0

print(f"\nPending surveys count: {pending_surveys}")
print(f"Surveys found: {surveys.count()}")

print("\n=== SURVEYS THAT SHOULD BE DISPLAYED ===")
for survey in surveys:
    print(f"  ID: {survey.id}")
    print(f"  Title: {survey.title}")
    print(f"  Status: {survey.status}")
    print(f"  Recipient: {survey.recipient_type}")
    print(f"  Created: {survey.created_at}")
    print()

# Now check what the template would receive
context = {
    "surveys": surveys,
    "pending_surveys": pending_surveys,
}

print("=== CONTEXT THAT WOULD BE PASSED TO TEMPLATE ===")
print(f"surveys: {list(surveys.values_list('id', 'title', 'status'))}")
print(f"pending_surveys: {pending_surveys}")
