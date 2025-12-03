#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Student, Survey
from django.contrib.auth.models import User

print("=" * 80)
print("COMPREHENSIVE SURVEY DEBUG REPORT")
print("=" * 80)

print("\n1. ALL SURVEYS IN DATABASE (sorted by ID desc):")
print("-" * 80)
all_surveys = Survey.objects.all().order_by('-id')
for survey in all_surveys:
    print(f"  ID: {survey.id:2d} | Status: {survey.status:6s} | Title: {survey.title[:40]:40s} | School: {survey.school.name[:30] if survey.school else 'None'}")

print("\n2. STUDENTS IN DATABASE:")
print("-" * 80)
for student in Student.objects.all():
    school_name = student.school.name if student.school else 'NONE (PROBLEM!)'
    print(f"  {student.user.username:30s} | School: {school_name}")

print("\n3. FILTERING LOGIC TEST (for each student):")
print("-" * 80)
for student in Student.objects.all():
    print(f"\n  Student: {student.user.username}")
    print(f"  School: {student.school.name if student.school else 'NONE'}")
    
    if not student.school:
        print(f"  ❌ ERROR: Student has no school assigned!")
        continue
    
    # This is the exact query from the view
    surveys = Survey.objects.filter(
        school=student.school,
        status='active',
        recipient_type__in=['students', 'both']
    ).order_by('-created_at')
    
    print(f"  ✅ Query returned {surveys.count()} surveys:")
    if surveys.exists():
        for survey in surveys:
            print(f"     - ID {survey.id}: {survey.title} (Status: {survey.status}, Recipient: {survey.recipient_type})")
    else:
        print(f"     (No active surveys for this student's school)")

print("\n4. SURVEY STATUS BREAKDOWN FOR EACH SCHOOL:")
print("-" * 80)
from core.models import School
for school in School.objects.all():
    surveys_for_school = Survey.objects.filter(school=school)
    if surveys_for_school.exists():
        print(f"\n  School: {school.name}")
        active = surveys_for_school.filter(status='active').count()
        closed = surveys_for_school.filter(status='closed').count()
        draft = surveys_for_school.filter(status='draft').count()
        print(f"    Active:  {active}")
        print(f"    Closed:  {closed}")
        print(f"    Draft:   {draft}")
        print(f"    Total:   {surveys_for_school.count()}")

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print("✅ The query ONLY returns surveys with status='active'")
print("✅ Closed/Draft surveys should NOT appear to students")
print("✅ If you see closed surveys, it's a caching or JavaScript issue")
print("\nTry:")
print("  1. Hard refresh browser (Ctrl+Shift+R on Windows)")
print("  2. Clear browser cache")
print("  3. Try incognito/private window")
print("=" * 80)
