#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Survey, Student

print("=" * 100)
print("TESTING MULTI-ADMIN SURVEY VISIBILITY FIX")
print("=" * 100)

# Get first student as test case
students = Student.objects.all()[:2]

for student in students:
    print(f"\n{'='*100}")
    print(f"STUDENT: {student.user.username}")
    print(f"SCHOOL: {student.school.name if student.school else 'No School'}")
    print(f"{'='*100}")
    
    # Simulate what the view does
    try:
        all_surveys = Survey.objects.filter(
            status='active',
            recipient_type__in=['students', 'both']
        ).order_by('-created_at')
        
        print(f"\n✓ ALL ACTIVE SURVEYS (visible to this student):")
        print("-" * 100)
        
        survey_list = []
        for survey in all_surveys:
            is_required = survey.school == student.school if student.school else False
            required_text = "🔴 REQUIRED" if is_required else "🟡 OPTIONAL"
            
            survey_list.append({
                'survey': survey,
                'is_required': is_required,
                'school_name': survey.school.name if survey.school else 'Unknown'
            })
            
            print(f"  ID {survey.id}: {survey.title}")
            print(f"    School: {survey.school.name if survey.school else 'Unknown'}")
            print(f"    Status: {required_text}")
            print(f"    Created by: {survey.created_by.username if survey.created_by else 'Unknown'}")
            print()
        
        print(f"Total surveys visible: {len(survey_list)}")
        print(f"Required (from this school): {sum(1 for s in survey_list if s['is_required'])}")
        print(f"Optional (from other schools): {sum(1 for s in survey_list if not s['is_required'])}")
        
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")

print(f"\n{'='*100}")
print("TEST COMPLETE")
print(f"{'='*100}\n")
