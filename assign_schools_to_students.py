#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from core.models import Student, School

# Get the main school (or first school)
try:
    school = School.objects.first()
    if not school:
        print("No schools found in database!")
        exit(1)
    
    print(f"Using school: {school.name}")
    
    # Update all students without a school
    students_without_school = Student.objects.filter(school__isnull=True)
    count = students_without_school.count()
    
    if count > 0:
        students_without_school.update(school=school)
        print(f"✅ Updated {count} students with school: {school.name}")
    else:
        print("✅ All students already have a school assigned")
    
    # Verify
    print("\n=== Updated Students ===")
    for student in Student.objects.all():
        print(f"  {student.user.username}: {student.school.name if student.school else 'None'}")
        
except Exception as e:
    print(f"Error: {e}")
