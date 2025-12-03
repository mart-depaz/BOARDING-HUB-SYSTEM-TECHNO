from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.db.utils import NotSupportedError
from functools import wraps
from collections import OrderedDict
from core.models import UserProfile, Property, Student, BoardingAssignment, EmergencyLog, MaintenanceRequest, Department, Program, Survey, SurveySection, SurveyQuestion, SurveyResponse, SurveyAnswer, TrashLog
from django.contrib.auth.models import User
from django.core.mail import send_mail
from core.email_backend import send_email_with_feedback
from django.conf import settings
import secrets
import string
import json


def school_admin_required(view_func):
    """Decorator to ensure only school admins can access a view"""
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # If not authenticated, redirect to student/owner login first
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in first using the student/owner login page.')
            return redirect('accounts:login')
        
        try:
            profile = request.user.profile
            if profile.role != 'school_admin':
                messages.error(request, 'Access denied. School administrators only. Please use the admin panel portal.')
                from django.contrib.auth import logout
                logout(request)
                return redirect('accounts:login')
        except UserProfile.DoesNotExist:
            messages.error(request, 'User profile not found. Please contact administrator.')
            from django.contrib.auth import logout
            logout(request)
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_login(request):
    """Dedicated login page for school administrators only - accessible by direct URL"""
    # If already authenticated as school admin, redirect to dashboard
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'school_admin':
                return redirect('admin_panel:dashboard')
            else:
                # If logged in but not school admin, logout and show admin login page
                from django.contrib.auth import logout
                logout(request)
                messages.error(request, 'This portal is for school administrators only.')
        except UserProfile.DoesNotExist:
            from django.contrib.auth import logout
            logout(request)
    
    # Allow direct access to admin login page by URL (no redirect)
    # This is safe because the URL is not publicly known
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        # Try to authenticate
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # Check if user is a school admin
            try:
                profile = user.profile
                if profile.role != 'school_admin':
                    messages.error(request, 'Access denied. This portal is for school administrators only.')
                    return render(request, 'admin_panel/admin_login.html')
                
                login(request, user)
                return redirect('admin_panel:dashboard')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found. Please contact administrator.')
        else:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'admin_panel/admin_login.html')


@school_admin_required
def dashboard(request):
    """School Admin Dashboard"""
    profile = request.user.profile
    
    # Get statistics
    total_students = Student.objects.filter(school=profile.school).count()
    total_properties = Property.objects.filter(school=profile.school).count()
    verified_properties = Property.objects.filter(school=profile.school, status='verified').count()
    
    # Get students with boarding assignments
    boarding_students = BoardingAssignment.objects.filter(
        student__school=profile.school,
        status='active'
    ).select_related('student', 'property')
    
    # Critical alerts (properties with low rating)
    low_rating_properties = Property.objects.filter(
        school=profile.school,
        safety_rating__lt=3.0,
        status='verified'
    ).count()
    
    # Critical safety alerts (emergency logs with high severity)
    critical_alerts = EmergencyLog.objects.filter(
        property__school=profile.school,
        severity__in=['high', 'critical'],
        status__in=['open', 'investigating']
    ).count()
    
    # Pending verifications (properties not yet verified)
    pending_verifications = Property.objects.filter(
        school=profile.school,
        status='pending'
    ).count()
    
    # Pending survey responses (students awaiting approval)
    pending_survey_responses = SurveyResponse.objects.filter(
        survey__school=profile.school,
        status='pending'
    ).count()
    
    # Recent alerts for the dashboard
    recent_alerts = EmergencyLog.objects.filter(
        property__school=profile.school
    ).select_related('property').order_by('-created_at')[:5]
    # Response counts per department for dashboard summary
    department_response_counts = []
    departments = Department.objects.filter(school=profile.school).order_by('name')
    for dept in departments:
        # Count responses linked to students in this department
        count1 = SurveyResponse.objects.filter(survey__school=profile.school, student__department=dept).count()
        # Try JSON contains lookup first; fall back to text search on DBs that don't support JSON contains (e.g., SQLite)
        try:
            count2 = SurveyResponse.objects.filter(
                survey__school=profile.school,
                additional_data__contains={"department_id": dept.id}
            ).count()
        except NotSupportedError:
            # SQLite doesn't support JSON contains; do a safe icontains fallback for common JSON key formats
            patterns = [f'"department_id": {dept.id}', f'"department_id":"{dept.id}"', f'"department_id": "{dept.id}"']
            q = Q()
            for p in patterns:
                q |= Q(additional_data__icontains=p)
            count2 = SurveyResponse.objects.filter(survey__school=profile.school).filter(q).count()

        department_response_counts.append({'department': dept.name, 'count': count1 + count2})
    
    context = {
        'total_students': total_students,
        'total_properties': total_properties,
        'verified_properties': verified_properties,
        'low_rating_properties': low_rating_properties,
        'critical_alerts': critical_alerts,
        'pending_verifications': pending_verifications,
        'pending_survey_responses': pending_survey_responses,
        'boarding_students': boarding_students[:10],  # Latest 10
        'recent_alerts': recent_alerts,
        'department_response_counts': department_response_counts,
        'department_response_counts_json': json.dumps(department_response_counts),
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


@school_admin_required
def database_view(request):
    """Database view showing all students and property owners with details"""
    from django.db.models import Q
    profile = request.user.profile
    
    # Get all students with their assignments
    students = Student.objects.filter(school=profile.school).select_related('user', 'department', 'program').prefetch_related('boarding_assignments__property')
    
    # Apply search filter (case-insensitive search by name or student ID)
    search_query = request.GET.get('search', '').strip()
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(student_id__icontains=search_query)
        )
    
    # Apply department filter
    department_id = request.GET.get('department', '').strip()
    if department_id:
        students = students.filter(department_id=department_id)
    
    # Apply program filter
    program_id = request.GET.get('program', '').strip()
    if program_id:
        students = students.filter(program_id=program_id)
    
    # Get all departments for filter dropdown
    departments = Department.objects.filter(school=profile.school).order_by('name')
    
    # Get all programs for filter dropdown (with department association)
    programs = Program.objects.filter(department__school=profile.school).select_related('department').order_by('department__name', 'name')
    
    # Get all property owners
    property_owners = UserProfile.objects.filter(
        school=profile.school,
        role='property_owner'
    ).select_related('user').prefetch_related('user__owned_properties')
    
    context = {
        'students': students,
        'property_owners': property_owners,
        'departments': departments,
        'programs': programs,
    }
    
    return render(request, 'admin_panel/database.html', context)


@school_admin_required
def property_audits(request):
    """Property Audits View"""
    profile = request.user.profile
    properties = Property.objects.filter(school=profile.school).select_related('owner', 'verified_by').order_by('-created_at')
    
    context = {
        'properties': properties,
    }
    
    return render(request, 'admin_panel/property_audits.html', context)


@school_admin_required
def boarding_students(request):
    """Boarding Students Management with Department/Program filtering"""
    profile = request.user.profile
    students = Student.objects.filter(school=profile.school).select_related('user', 'department', 'program').order_by('student_id')
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    department_id = request.GET.get('department', '')
    program_id = request.GET.get('program', '')
    
    # Apply filters
    if search_query:
        students = students.filter(
            Q(student_id__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    if department_id:
        students = students.filter(department_id=department_id)
    
    if program_id:
        students = students.filter(program_id=program_id)
    
    # Get departments and programs for filter dropdowns
    departments = Department.objects.filter(school=profile.school, is_active=True).order_by('name')
    programs = Program.objects.filter(department__school=profile.school, is_active=True).select_related('department').order_by('name')
    
    context = {
        'students': students,
        'search_query': search_query,
        'departments': departments,
        'programs': programs,
        'selected_department': department_id,
        'selected_program': program_id,
    }
    
    return render(request, 'admin_panel/boarding_students.html', context)


@school_admin_required
def emergency_log(request):
    """Emergency Log View"""
    profile = request.user.profile
    emergencies = EmergencyLog.objects.filter(
        property__school=profile.school
    ).select_related('property', 'student', 'reported_by').order_by('-created_at')[:50]
    
    context = {
        'emergencies': emergencies,
    }
    
    return render(request, 'admin_panel/emergency_log.html', context)


@school_admin_required
def provisioning_hub(request):
    """Provisioning Hub - Add Students and Property Owners"""
    profile = request.user.profile
    
    # Get all properties and students for display
    properties = Property.objects.filter(school=profile.school).select_related('owner').order_by('-created_at')
    students = Student.objects.filter(school=profile.school).select_related('user').order_by('-created_at')
    
    # Get departments and programs for student enrollment form
    departments = Department.objects.filter(school=profile.school, is_active=True).order_by('name')
    programs = Program.objects.filter(department__school=profile.school, is_active=True).select_related('department').order_by('name')
    
    context = {
        'properties': properties,
        'students': students,
        'active_properties': properties.filter(status='verified').count(),
        'has_properties': properties.exists(),
        'has_students': students.exists(),
        'departments': departments,
        'programs': programs,
    }
    
    return render(request, 'admin_panel/provisioning_hub.html', context)


@school_admin_required
def add_property_owner(request):
    """Add new property owner"""
    if request.method != 'POST':
        return redirect('admin_panel:provisioning_hub')
    
    profile = request.user.profile
    property_id = request.POST.get('prop-id', '').strip().upper()
    owner_name = request.POST.get('owner-name', '').strip()
    owner_email = request.POST.get('owner-email', '').strip().lower()
    address = request.POST.get('address', '').strip()
    
    # Validation
    if not all([property_id, owner_name, owner_email, address]):
        messages.error(request, 'All fields are required.')
        return redirect('admin_panel:provisioning_hub')
    
    # Check if property ID already exists
    if Property.objects.filter(property_id=property_id).exists():
        messages.error(request, f'Property ID {property_id} already exists.')
        return redirect('admin_panel:provisioning_hub')
    
    # Generate random password (8 uppercase letters)
    temp_password = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(8))
    
    # Create or get user
    user, created = User.objects.get_or_create(
        username=owner_email,
        defaults={
            'email': owner_email,
            'first_name': owner_name.split()[0] if owner_name.split() else '',
            'last_name': ' '.join(owner_name.split()[1:]) if len(owner_name.split()) > 1 else '',
        }
    )
    
    if not created:
        messages.error(request, 'Email already registered.')
        return redirect('admin_panel:provisioning_hub')
    
    # Set password
    user.set_password(temp_password)
    user.save()
    
    # Create profile
    UserProfile.objects.create(
        user=user,
        role='property_owner',
        school=profile.school
    )
    
    # Create property
    property_obj = Property.objects.create(
        property_id=property_id,
        owner=user,
        school=profile.school,
        address=address,
        status='pending'
    )
    
    # Send email with login credentials
    try:
        login_url = request.build_absolute_uri('/login/')
        subject = f'Welcome to {profile.school.name} Boarding Hub System'
        message = f'''Dear {owner_name},

Welcome to the {profile.school.name} Boarding Hub System!

Your account has been created successfully. Below are your login credentials:

Property ID: {property_id}
Email: {owner_email}
Password: {temp_password}

IMPORTANT SECURITY NOTICE:
- Please keep this password confidential and do not share it with anyone.
- We recommend changing your password after your first login.
- Never share your login credentials with others.

You can now log in to the system using your email or property ID and the password provided above.

Login URL: {login_url}

If you have any questions or need assistance, please contact the school administration.

Best regards,
{profile.school.name} Administration Team'''
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)
        print(f"Attempting to send email to {owner_email} from {from_email}")
        print(f"SMTP Host: {settings.EMAIL_HOST}, Port: {settings.EMAIL_PORT}")
        
        send_mail(
            subject,
            message,
            from_email,
            [owner_email],
            fail_silently=False,
        )
        print(f"Email sent successfully to {owner_email}")
        messages.success(request, f'Property {property_id} and owner registered successfully. Login credentials sent to {owner_email}. If not received, check spam folder or sent_emails folder. Emails may take 1-5 minutes to arrive on phone.')
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_type = type(e).__name__
        full_traceback = traceback.format_exc()
        
        # Print detailed error to console
        print("=" * 60)
        print("EMAIL SENDING ERROR:")
        print(f"Error Type: {error_type}")
        print(f"Error Message: {error_msg}")
        print(f"Full Traceback:\n{full_traceback}")
        print("=" * 60)
        
        # Provide user-friendly error message
        if "authentication failed" in str(e).lower() or "535" in str(e) or "534" in str(e):
            user_error = f'⚠️ Email authentication failed! Gmail requires an App Password (not your regular password). The email was saved to sent_emails folder. Generate App Password at: https://myaccount.google.com/apppasswords'
        elif "connection" in str(e).lower() or "timeout" in str(e).lower():
            user_error = f'⚠️ Could not connect to email server. The email was saved to sent_emails folder. Check your internet connection.'
        else:
            user_error = f'⚠️ Email could not be sent via SMTP. The email was saved to sent_emails folder. Error: {error_msg[:100]}'
        
        messages.warning(request, f'Property {property_id} and owner registered successfully. {user_error} Password: {temp_password} (Check sent_emails folder for email content)')
    
    return redirect('admin_panel:provisioning_hub')


@school_admin_required
def add_student(request):
    """Add new student"""
    if request.method != 'POST':
        return redirect('admin_panel:provisioning_hub')
    
    profile = request.user.profile
    student_id = request.POST.get('student-id', '').strip().upper()
    student_name = request.POST.get('student-name', '').strip()
    student_email = request.POST.get('student-email', '').strip().lower()
    assigned_prop_id = request.POST.get('assigned-prop-id', '').strip()
    department_id = request.POST.get('department', '').strip()
    program_id = request.POST.get('program', '').strip()
    
    # Validation
    if not all([student_id, student_name, student_email]):
        messages.error(request, 'Student ID, name, and email are required.')
        return redirect('admin_panel:provisioning_hub')
    
    # Check if student ID already exists
    if Student.objects.filter(student_id=student_id).exists():
        messages.error(request, f'Student ID {student_id} already exists.')
        return redirect('admin_panel:provisioning_hub')
    
    # Generate temporary password (8 uppercase letters)
    temp_password = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(8))
    
    # Create user
    user, created = User.objects.get_or_create(
        username=student_email,
        defaults={
            'email': student_email,
            'first_name': student_name.split()[0] if student_name.split() else '',
            'last_name': ' '.join(student_name.split()[1:]) if len(student_name.split()) > 1 else '',
        }
    )
    
    if not created:
        messages.error(request, 'Email already registered.')
        return redirect('admin_panel:provisioning_hub')
    
    # Set password
    user.set_password(temp_password)
    user.save()
    
    # Create profile
    UserProfile.objects.create(
        user=user,
        role='student',
        school=profile.school
    )
    
    # Get department and program if provided
    department = None
    program = None
    if department_id:
        try:
            department = Department.objects.get(id=department_id, school=profile.school)
        except Department.DoesNotExist:
            pass
    
    if program_id:
        try:
            program = Program.objects.get(id=program_id, department__school=profile.school)
            if department and program.department != department:
                program = None
        except Program.DoesNotExist:
            pass
    
    # Create student
    student = Student.objects.create(
        user=user,
        student_id=student_id,
        school=profile.school,
        department=department,
        program=program
    )
    
    # Assign to property if provided
    if assigned_prop_id:
        try:
            property_obj = Property.objects.get(property_id=assigned_prop_id, school=profile.school)
            BoardingAssignment.objects.create(
                student=student,
                property=property_obj,
                status='pending'
            )
        except Property.DoesNotExist:
            messages.warning(request, f'Property {assigned_prop_id} not found. Student created without property assignment.')
    
    # Send email with login credentials
    try:
        login_url = request.build_absolute_uri('/login/')
        subject = f'Welcome to {profile.school.name} Boarding Hub System'
        message = f'''Dear {student_name},

Welcome to the {profile.school.name} Boarding Hub System!

Your student account has been created successfully. Below are your login credentials:

Student ID: {student_id}
Email: {student_email}
Password: {temp_password}

IMPORTANT SECURITY NOTICE:
- Please keep this password confidential and do not share it with anyone.
- We recommend changing your password after your first login.
- Never share your login credentials with others.

You can now log in to the system using your email, student ID, or the password provided above.

Login URL: {login_url}

If you have any questions or need assistance, please contact the school administration.

Best regards,
{profile.school.name} Administration Team'''
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)
        print(f"Attempting to send email to {student_email} from {from_email}")
        print(f"SMTP Host: {settings.EMAIL_HOST}, Port: {settings.EMAIL_PORT}")
        
        send_mail(
            subject,
            message,
            from_email,
            [student_email],
            fail_silently=False,
        )
        print(f"Email sent successfully to {student_email}")
        messages.success(request, f'Student {student_id} enrolled successfully. Login credentials sent to {student_email}. If not received, check spam folder or sent_emails folder. Emails may take 1-5 minutes to arrive on phone.')
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_type = type(e).__name__
        full_traceback = traceback.format_exc()
        
        # Print detailed error to console
        print("=" * 60)
        print("EMAIL SENDING ERROR:")
        print(f"Error Type: {error_type}")
        print(f"Error Message: {error_msg}")
        print(f"Full Traceback:\n{full_traceback}")
        print("=" * 60)
        
        # Provide user-friendly error message
        if "authentication failed" in str(e).lower() or "535" in str(e) or "534" in str(e):
            user_error = f'⚠️ Email authentication failed! Gmail requires an App Password (not your regular password). The email was saved to sent_emails folder. Generate App Password at: https://myaccount.google.com/apppasswords'
        elif "connection" in str(e).lower() or "timeout" in str(e).lower():
            user_error = f'⚠️ Could not connect to email server. The email was saved to sent_emails folder. Check your internet connection.'
        else:
            user_error = f'⚠️ Email could not be sent via SMTP. The email was saved to sent_emails folder. Error: {error_msg[:100]}'
        
        messages.warning(request, f'Student {student_id} enrolled successfully. {user_error} Password: {temp_password} (Check sent_emails folder for email content)')
    
    return redirect('admin_panel:provisioning_hub')


@school_admin_required
def manage_departments(request):
    """Manage Departments"""
    profile = request.user.profile
    departments = Department.objects.filter(school=profile.school).order_by('name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            
            if not name:
                messages.error(request, 'Department name is required.')
            else:
                department, created = Department.objects.get_or_create(
                    school=profile.school,
                    name=name,
                    defaults={'code': code, 'description': description}
                )
                if created:
                    messages.success(request, f'Department "{name}" added successfully.')
                else:
                    messages.error(request, f'Department "{name}" already exists.')
        
        elif action == 'edit':
            dept_id = request.POST.get('department_id')
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            
            try:
                department = Department.objects.get(id=dept_id, school=profile.school)
                department.name = name
                department.code = code
                department.description = description
                department.save()
                messages.success(request, f'Department "{name}" updated successfully.')
            except Department.DoesNotExist:
                messages.error(request, 'Department not found.')
        
        elif action == 'delete':
            dept_id = request.POST.get('department_id')
            try:
                department = Department.objects.get(id=dept_id, school=profile.school)
                # Check if department has students
                if department.students.exists():
                    messages.error(request, f'Cannot delete "{department.name}" because it has students assigned.')
                else:
                    department.delete()
                    messages.success(request, f'Department "{department.name}" deleted successfully.')
            except Department.DoesNotExist:
                messages.error(request, 'Department not found.')
        
        elif action == 'toggle':
            dept_id = request.POST.get('department_id')
            try:
                department = Department.objects.get(id=dept_id, school=profile.school)
                department.is_active = not department.is_active
                department.save()
                status = 'activated' if department.is_active else 'deactivated'
                messages.success(request, f'Department "{department.name}" {status} successfully.')
            except Department.DoesNotExist:
                messages.error(request, 'Department not found.')
        
        return redirect('admin_panel:manage_departments')
    
    context = {
        'departments': departments,
    }
    
    return render(request, 'admin_panel/manage_departments.html', context)


@school_admin_required
def manage_programs(request):
    """Manage Programs"""
    profile = request.user.profile
    programs = Program.objects.filter(department__school=profile.school).select_related('department').order_by('department__name', 'name')
    departments = Department.objects.filter(school=profile.school, is_active=True).order_by('name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            department_id = request.POST.get('department_id')
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            
            if not name or not department_id:
                messages.error(request, 'Program name and department are required.')
            else:
                try:
                    department = Department.objects.get(id=department_id, school=profile.school)
                    program, created = Program.objects.get_or_create(
                        department=department,
                        name=name,
                        defaults={'code': code, 'description': description}
                    )
                    if created:
                        messages.success(request, f'Program "{name}" added successfully.')
                    else:
                        messages.error(request, f'Program "{name}" already exists in this department.')
                except Department.DoesNotExist:
                    messages.error(request, 'Department not found.')
        
        elif action == 'edit':
            program_id = request.POST.get('program_id')
            department_id = request.POST.get('department_id')
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            
            try:
                program = Program.objects.get(id=program_id, department__school=profile.school)
                department = Department.objects.get(id=department_id, school=profile.school)
                program.department = department
                program.name = name
                program.code = code
                program.description = description
                program.save()
                messages.success(request, f'Program "{name}" updated successfully.')
            except (Program.DoesNotExist, Department.DoesNotExist):
                messages.error(request, 'Program or department not found.')
        
        elif action == 'delete':
            program_id = request.POST.get('program_id')
            try:
                program = Program.objects.get(id=program_id, department__school=profile.school)
                # Check if program has students
                if program.students.exists():
                    messages.error(request, f'Cannot delete "{program.name}" because it has students assigned.')
                else:
                    program.delete()
                    messages.success(request, f'Program "{program.name}" deleted successfully.')
            except Program.DoesNotExist:
                messages.error(request, 'Program not found.')
        
        elif action == 'toggle':
            program_id = request.POST.get('program_id')
            try:
                program = Program.objects.get(id=program_id, department__school=profile.school)
                program.is_active = not program.is_active
                program.save()
                status = 'activated' if program.is_active else 'deactivated'
                messages.success(request, f'Program "{program.name}" {status} successfully.')
            except Program.DoesNotExist:
                messages.error(request, 'Program not found.')
        
        return redirect('admin_panel:manage_programs')
    
    context = {
        'programs': programs,
        'departments': departments,
    }
    
    return render(request, 'admin_panel/manage_programs.html', context)


@school_admin_required
def edit_student(request, student_id):
    """Edit student information"""
    profile = request.user.profile
    student = get_object_or_404(Student, id=student_id, school=profile.school)
    
    if request.method == 'POST':
        # Update student fields
        student.student_id = request.POST.get('student_id', student.student_id).strip()
        department_id = request.POST.get('department')
        program_id = request.POST.get('program')
        year_level = request.POST.get('year_level', '').strip()
        date_of_birth = request.POST.get('date_of_birth') or None
        emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        
        # Update user fields
        user = student.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save()
        
        # Update student fields
        if department_id:
            try:
                student.department = Department.objects.get(id=department_id, school=profile.school)
            except Department.DoesNotExist:
                student.department = None
        else:
            student.department = None
        
        if program_id:
            try:
                program = Program.objects.get(id=program_id, department__school=profile.school)
                # Ensure program matches selected department
                if student.department and program.department == student.department:
                    student.program = program
                elif not student.department:
                    student.program = program
                else:
                    student.program = None
            except Program.DoesNotExist:
                student.program = None
        else:
            student.program = None
        
        student.year_level = year_level
        student.date_of_birth = date_of_birth
        student.emergency_contact_name = emergency_contact_name
        student.emergency_contact_phone = emergency_contact_phone
        student.save()
        
        messages.success(request, f'Student {student.student_id} updated successfully.')
        return redirect('admin_panel:students')
    
    departments = Department.objects.filter(school=profile.school, is_active=True).order_by('name')
    programs = Program.objects.filter(department__school=profile.school, is_active=True).select_related('department').order_by('name')
    
    context = {
        'student': student,
        'departments': departments,
        'programs': programs,
    }
    
    return render(request, 'admin_panel/edit_student.html', context)


@school_admin_required
def admin_profile(request):
    """Admin Profile Management"""
    profile = request.user.profile
    
    if request.method == 'POST':
        # Update user fields
        user = request.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        
        # Update password if provided
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
            else:
                user.set_password(new_password)
                messages.success(request, 'Password updated successfully.')
        
        user.save()
        
        # Update profile fields
        profile.phone = request.POST.get('phone', '').strip()
        profile.save()
        
        # Update school Facebook URL
        if profile.school:
            facebook_url = request.POST.get('facebook_url', '').strip()
            profile.school.facebook_url = facebook_url
            profile.school.save()
        
        messages.success(request, 'Profile updated successfully.')
        return redirect('admin_panel:admin_profile')
    
    context = {
        'profile': profile,
    }
    
    return render(request, 'admin_panel/admin_profile.html', context)


# ==================== SURVEY MANAGEMENT ====================

@school_admin_required
def survey_list(request):
    """List all surveys"""
    profile = request.user.profile
    # Exclude surveys that were moved to trash (status 'closed') so deleted surveys don't appear here
    surveys = Survey.objects.filter(school=profile.school).exclude(status='closed').order_by('-created_at')
    
    context = {
        'surveys': surveys,
    }
    
    return render(request, 'admin_panel/survey_list.html', context)


@school_admin_required
def survey_create(request):
    """Create or edit survey"""
    profile = request.user.profile
    
    if request.method == 'POST':
        import json
        import uuid
        
        # Get survey data from POST
        survey_id = request.POST.get('survey_id')
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', '').strip()
        description = request.POST.get('description', '').strip()
        status = request.POST.get('status', 'draft')
        require_property_info = request.POST.get('require_property_info') == 'on'
        
        if not title:
            messages.error(request, 'Survey title is required.')
            return redirect('admin_panel:survey_create')
        
        # Create or update survey
        if survey_id:
            survey = get_object_or_404(Survey, id=survey_id, school=profile.school)
            survey.title = title
            if category:
                survey.category = category
            survey.description = description
            survey.status = status
            survey.require_property_info = require_property_info
            survey.save()
        else:
            # Generate unique code
            unique_code = f"SURV-{uuid.uuid4().hex[:8].upper()}"
            while Survey.objects.filter(unique_code=unique_code).exists():
                unique_code = f"SURV-{uuid.uuid4().hex[:8].upper()}"
            
            survey = Survey.objects.create(
                school=profile.school,
                title=title,
                category=category or 'Student Registration',
                description=description,
                status=status,
                unique_code=unique_code,
                require_property_info=require_property_info,
                created_by=request.user
            )
        
        # Handle sections and questions
        sections_data = json.loads(request.POST.get('sections', '[]'))
        
        # Delete existing sections if editing
        if survey_id:
            survey.sections.all().delete()
        
        # Create sections and questions
        for section_idx, section_data in enumerate(sections_data):
            section = SurveySection.objects.create(
                survey=survey,
                title=section_data.get('title', f'Section {section_idx + 1}'),
                color=section_data.get('color', '#818cf8'),
                order=section_idx
            )
            
            # Create questions
            questions = section_data.get('questions', [])
            for q_idx, question_data in enumerate(questions):
                SurveyQuestion.objects.create(
                    section=section,
                    text=question_data.get('text', ''),
                    question_type=question_data.get('type', 'text_short'),
                    options=question_data.get('options', []),
                    is_required=question_data.get('is_required', True),
                    order=q_idx
                )
        
        if survey_id:
            messages.success(request, f'Survey "{survey.title}" updated successfully!')
        else:
            messages.success(request, f'Survey "{survey.title}" created successfully!')
        return redirect('admin_panel:survey_detail', survey_id=survey.id)
    
    # GET request - show form
    survey_id = request.GET.get('id')
    survey = None
    sections = []
    if survey_id:
        survey = get_object_or_404(Survey, id=survey_id, school=profile.school)
        # Load existing sections and questions
        sections = survey.sections.all().prefetch_related('questions')
    
    # Get properties for property selection in survey
    properties = Property.objects.filter(school=profile.school, status='verified').order_by('property_id')
    # Departments and programs for preview/selection
    departments = Department.objects.filter(school=profile.school, is_active=True).order_by('name')
    programs = Program.objects.filter(department__school=profile.school, is_active=True).select_related('department').order_by('name')
    
    context = {
        'survey': survey,
        'sections': sections,
        'properties': properties,
        'departments': departments,
        'programs': programs,
    }
    
    return render(request, 'admin_panel/survey_create.html', context)


@school_admin_required
def survey_detail(request, survey_id):
    """View survey details and share link"""
    profile = request.user.profile
    survey = get_object_or_404(Survey, id=survey_id, school=profile.school)
    
    # Get response count (excluding deleted)
    all_responses = survey.responses.filter(deleted_at__isnull=True)
    response_count = all_responses.count()
    pending_count = all_responses.filter(status='pending').count()
    registered_count = all_responses.filter(status='registered').count()
    
    # Get survey sections and questions for layout preview
    sections = survey.sections.all().prefetch_related('questions').order_by('order')
    
    context = {
        'survey': survey,
        'response_count': response_count,
        'pending_count': pending_count,
        'registered_count': registered_count,
        'shareable_link': survey.get_shareable_link(request),
        'sections': sections,
    }
    
    return render(request, 'admin_panel/survey_detail.html', context)


@school_admin_required
def survey_responses(request, survey_id):
    """View all survey responses"""
    profile = request.user.profile
    survey = get_object_or_404(Survey, id=survey_id, school=profile.school)
    from django.utils import timezone
    # Handle bulk actions (approve/reject) from the admin list
    if request.method == 'POST' and request.POST.get('bulk_action'):
        action = request.POST.get('bulk_action')
        selected = request.POST.getlist('selected')
        processed = 0
        for rid in selected:
            try:
                resp = SurveyResponse.objects.get(id=int(rid), survey=survey)
            except Exception:
                continue

            if action == 'approve' and resp.status != 'registered':
                # Minimal approve flow: create user/profile/student and mark registered
                temp_password = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(8))
                try:
                    user, created = User.objects.get_or_create(
                        username=resp.student_email,
                        defaults={
                            'email': resp.student_email,
                            'first_name': resp.student_name.split()[0] if resp.student_name.split() else '',
                            'last_name': ' '.join(resp.student_name.split()[1:]) if len(resp.student_name.split()) > 1 else '',
                        }
                    )
                    user.set_password(temp_password)
                    user.save()

                    # Ensure profile
                    try:
                        prof = user.profile
                        if prof.role != 'student':
                            prof.role = 'student'
                        if not prof.school:
                            prof.school = profile.school
                        prof.save()
                    except UserProfile.DoesNotExist:
                        UserProfile.objects.create(user=user, role='student', school=profile.school)

                    # Create Student record if missing
                    if not hasattr(user, 'student_profile'):
                        Student.objects.create(
                            user=user,
                            student_id=resp.provided_student_id or f"S-{secrets.token_hex(4).upper()}",
                            school=profile.school
                        )
                except Exception:
                    pass

                resp.status = 'registered'
                resp.reviewed_by = request.user
                resp.reviewed_at = timezone.now()
                resp.save()
                processed += 1

            elif action == 'reject' and resp.status != 'rejected':
                resp.status = 'rejected'
                resp.reviewed_by = request.user
                resp.reviewed_at = timezone.now()
                resp.save()
                processed += 1

        messages.success(request, f'{processed} response(s) processed.')
        return redirect('admin_panel:survey_responses', survey_id=survey.id)
    
    # Check if viewing trash
    show_trash = request.GET.get('trash') == '1'
    
    if show_trash:
        # Show only deleted responses
        responses = SurveyResponse.objects.filter(survey=survey, deleted_at__isnull=False).order_by('-deleted_at')
    else:
        # Show only non-deleted responses
        responses = SurveyResponse.objects.filter(survey=survey, deleted_at__isnull=True).order_by('-created_at')
    
    # Calculate counts for each status (excluding deleted)
    all_responses = survey.responses.filter(deleted_at__isnull=True)
    all_count = all_responses.count()
    pending_count = all_responses.filter(status='pending').count()
    rejected_count = all_responses.filter(status='rejected').count()
    registered_count = all_responses.filter(status='registered').count()
    trash_count = survey.responses.filter(deleted_at__isnull=False).count()
    
    # Filter by status if provided (only if not viewing trash)
    status_filter = request.GET.get('status')
    if status_filter and not show_trash:
        responses = responses.filter(status=status_filter)

    # Attach department/program display attributes for organization in template
    for resp in responses:
        dept_name = None
        prog_name = None
        try:
            if resp.student and resp.student.department:
                dept_name = resp.student.department.code or resp.student.department.name
            elif resp.additional_data:
                dept_id = resp.additional_data.get('department_id')
                if dept_id:
                    try:
                        dept = Department.objects.filter(id=int(dept_id), school=profile.school).first()
                        if dept:
                            dept_name = dept.code or dept.name
                    except Exception:
                        pass

            if resp.student and resp.student.program:
                prog_name = resp.student.program.code or resp.student.program.name
            elif resp.additional_data:
                prog_id = resp.additional_data.get('program_id')
                if prog_id:
                    try:
                        prog = Program.objects.filter(id=int(prog_id), department__school=profile.school).first()
                        if prog:
                            prog_name = prog.code or prog.name
                    except Exception:
                        pass
        except Exception:
            dept_name = None
            prog_name = None

        resp.dept_display = dept_name or '—'
        resp.prog_display = prog_name or '—'
    # Group responses by department -> program for easier UI rendering
    grouped_responses = OrderedDict()
    for resp in responses:
        dept = getattr(resp, 'dept_display', '—') or '—'
        prog = getattr(resp, 'prog_display', '—') or '—'
        if dept not in grouped_responses:
            grouped_responses[dept] = OrderedDict()
        if prog not in grouped_responses[dept]:
            grouped_responses[dept][prog] = []
        grouped_responses[dept][prog].append(resp)

    context = {
        'survey': survey,
        'responses': responses,
        'grouped_responses': grouped_responses,
        'status_filter': status_filter,
        'show_trash': show_trash,
        'all_count': all_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'registered_count': registered_count,
        'trash_count': trash_count,
    }
    
    return render(request, 'admin_panel/survey_responses.html', context)


@school_admin_required
def survey_response_detail(request, response_id):
    """View and review individual survey response"""
    profile = request.user.profile
    response = get_object_or_404(SurveyResponse, id=response_id, survey__school=profile.school)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Approve the response: set to 'registered' immediately and auto-create student/user
            response.status = 'registered'
            response.reviewed_by = request.user
            from django.utils import timezone
            response.reviewed_at = timezone.now()
            response.review_notes = request.POST.get('notes', '')

            # Generate a temporary password
            temp_password = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(8))

            # Create or update user with email as username
            try:
                user, created = User.objects.get_or_create(
                    username=response.student_email,
                    defaults={
                        'email': response.student_email,
                        'first_name': response.student_name.split()[0] if response.student_name.split() else '',
                        'last_name': ' '.join(response.student_name.split()[1:]) if len(response.student_name.split()) > 1 else '',
                    }
                )

                # If user exists, perform safe checks
                if not created:
                    try:
                        profile_obj = user.profile
                        # Prevent overwriting school_admin accounts
                        if profile_obj.role == 'school_admin':
                            messages.error(request, 'This email belongs to a school administrator. Cannot create student account using this email.')
                            return redirect('admin_panel:survey_response_detail', response_id=response_id)
                    except UserProfile.DoesNotExist:
                        profile_obj = None

                # Set the password (overwrite existing password)
                user.set_password(temp_password)
                user.save()

                # Ensure user has a profile and is marked as student for this school
                if not hasattr(user, 'profile') or profile_obj is None:
                    UserProfile.objects.create(
                        user=user,
                        role='student',
                        school=profile.school,
                        is_outsider=False
                    )
                else:
                    # Update profile to student role and assign school if missing
                    if profile_obj.role != 'student':
                        profile_obj.role = 'student'
                    if not profile_obj.school:
                        profile_obj.school = profile.school
                    profile_obj.save()

                # Clear any previous password setup tokens on the response
                response.password_setup_token = None
                response.password_setup_token_expires = None
                
                # At approval time, automatically create a Student record so the student is registered immediately
                student = None
                student_msg = ''
                assignment_msg = ''
                
                # STEP 1: Determine student_id (use provided or additional_data or generate)
                provided_id = response.provided_student_id or (response.additional_data.get('student_id') if response.additional_data else None)
                student_id_val = provided_id or f"S-{secrets.token_hex(4).upper()}"
                # Ensure unique student_id
                while Student.objects.filter(student_id=student_id_val).exists():
                    student_id_val = f"S-{secrets.token_hex(4).upper()}"

                # STEP 2: Resolve department/program from response.additional_data if present
                dept = None
                prog = None
                try:
                    if response.additional_data:
                        dept_id = response.additional_data.get('department_id')
                        prog_id = response.additional_data.get('program_id')
                        
                        # Handle both string and integer IDs
                        if dept_id:
                            try:
                                dept_id = int(dept_id)
                            except (ValueError, TypeError):
                                dept_id = None
                            
                            if dept_id:
                                dept = Department.objects.filter(id=dept_id, school=profile.school).first()
                        
                        if prog_id:
                            try:
                                prog_id = int(prog_id)
                            except (ValueError, TypeError):
                                prog_id = None
                            
                            if prog_id:
                                prog = Program.objects.filter(id=prog_id, department__school=profile.school).first()
                except Exception as e:
                    print(f"Warning: Failed to resolve department/program: {e}")
                    dept = None
                    prog = None

                # STEP 3: Check if student already exists
                try:
                    if hasattr(user, 'student_profile'):
                        student = user.student_profile
                        student_msg = f'✓ Student {student.student_id} already exists.'
                except Exception:
                    student = None

                # STEP 4: Create Student if not already linked
                if not student:
                    try:
                        student = Student.objects.create(
                            user=user,
                            student_id=student_id_val,
                            school=profile.school,
                            department=dept,
                            program=prog,
                            date_of_birth=(response.additional_data.get('date_of_birth') if response.additional_data else None),
                            emergency_contact_name=(response.additional_data.get('emergency_contact_name') if response.additional_data else ''),
                            emergency_contact_phone=(response.student_phone or (response.additional_data.get('emergency_contact_phone') if response.additional_data else '')),
                        )
                        student_msg = f'✓ Student {student.student_id} created with {student.department.name if student.department else "unassigned"} department and {student.program.name if student.program else "unassigned"} program.'
                        print(f"DEBUG: Student created successfully: {student.student_id}")
                    except Exception as e:
                        print(f"ERROR: Failed to create Student: {e}")
                        import traceback
                        print(traceback.format_exc())
                        messages.error(request, f'CRITICAL ERROR: Failed to create Student record: {str(e)[:100]}')
                        # Still mark response as registered even if student creation failed
                        response.status = 'registered'
                        response.reviewed_by = request.user
                        from django.utils import timezone
                        response.reviewed_at = timezone.now()
                        response.review_notes = request.POST.get('notes', '')
                        response.save()
                        return redirect('admin_panel:survey_responses', survey_id=response.survey.id) + '?status=pending'

                # STEP 5: Link response to student
                try:
                    response.student = student
                    response.save()
                    print(f"DEBUG: Response {response.id} linked to student {student.student_id}")
                except Exception as e:
                    print(f"WARNING: Failed to link response to student: {e}")
                    messages.warning(request, f'Student created but could not link response: {str(e)[:100]}')

                # STEP 6: Try to create boarding assignment if property exists
                try:
                    prop = None
                    if response.additional_data:
                        owner_email = response.additional_data.get('property_owner_email')
                        prop_name = response.additional_data.get('property_name')
                        if owner_email:
                            owner_user = User.objects.filter(email__iexact=owner_email).first()
                            if owner_user:
                                prop = Property.objects.filter(owner=owner_user, school=profile.school).first()
                        if not prop and prop_name:
                            prop = Property.objects.filter(name__icontains=prop_name, school=profile.school).first()

                    if prop:
                        # Determine assignment status: active if available, else pending
                        assignment_status = 'active' if prop.is_available else 'pending'
                        BoardingAssignment.objects.get_or_create(
                            student=student,
                            property=prop,
                            defaults={'status': assignment_status}
                        )
                        if assignment_status == 'active':
                            prop.current_occupancy = (prop.current_occupancy or 0) + 1
                            prop.save()
                        assignment_msg = f' Student assigned to {prop.property_id} ({assignment_status}).'
                        print(f"DEBUG: Student assigned to property {prop.property_id}")
                    else:
                        assignment_msg = f' Student registered but not assigned to any property.'
                except Exception as e:
                    print(f"WARNING: Failed to create boarding assignment: {e}")
                    assignment_msg = f' Student registered but assignment creation failed: {str(e)[:50]}'
                    # Don't fail the whole process if assignment fails
                
                # STEP 7: Show success message
                try:
                    messages.success(request, f'Approval complete!{student_msg}{assignment_msg}')
                except Exception as e:
                    print(f"WARNING: Failed to show success message: {e}")



                # Send email with generated password
                try:
                    from django.conf import settings

                    login_url = request.build_absolute_uri('/login/')
                    subject = f'Your Account Has Been Approved - {profile.school.name}'
                    message = f'''Dear {response.student_name},

Your survey response for {response.survey.title} has been approved by the school administrator.

An account has been created for you. You can log in using your email and the temporary password below. Please change your password after your first login.

Email: {response.student_email}
Temporary Password: {temp_password}

Login URL: {login_url}

IMPORTANT SECURITY NOTICE:
- Please keep this password confidential and do not share it with anyone.
- We recommend changing your password after your first login.

If you did not submit this survey, please contact the school administrator.

Best regards,
{profile.school.name} Administration Team
'''

                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)
                    print(f"\n{'='*60}")
                    print(f"ATTEMPTING TO SEND APPROVAL CREDENTIALS EMAIL")
                    print(f"{'='*60}")
                    print(f"To: {response.student_email}")
                    print(f"From: {from_email}")
                    print(f"Subject: {subject}")
                    print(f"{'='*60}\n")

                    used_fallback, result, saved_file = send_email_with_feedback(
                        subject,
                        message,
                        from_email,
                        [response.student_email],
                    )
                    print(f"\n✓ send_email_with_feedback() returned: {result}; fallback={used_fallback}; saved_file={saved_file}")
                    if used_fallback:
                        extra = f" Email content saved to: {saved_file}." if saved_file else ''
                        messages.warning(request, f'Response approved, but SMTP failed and the email was saved to the server (sent_emails). Please fix SMTP settings or manually forward the temporary password to {response.student_email}.{extra}')
                    else:
                        messages.success(request, f'Response approved. Login credentials have been sent to {response.student_email}. The student should check their inbox, spam folder, and wait 1-5 minutes for delivery.')
                except Exception as e:
                    import traceback
                    error_msg = str(e)
                    error_trace = traceback.format_exc()
                    print(f"\n{'='*60}")
                    print(f"ERROR SENDING APPROVAL CREDENTIALS EMAIL")
                    print(f"{'='*60}")
                    print(f"Error: {error_msg}")
                    print(f"Traceback:\n{error_trace}")
                    print(f"{'='*60}\n")
                    messages.warning(request, f'Response approved, but email could not be sent. Error: {error_msg[:100]}. Please contact the student manually with the temporary password.')
            except Exception as e:
                import traceback
                print(f"Error during approval/user creation: {traceback.format_exc()}")
                messages.error(request, 'An error occurred while creating the user account. Please try again or contact support.')
            
            # Always save the response with registered status after approval attempt
            response.save()
            
        elif action == 'reject':
            response.status = 'rejected'
            response.reviewed_by = request.user
            from django.utils import timezone
            response.reviewed_at = timezone.now()
            response.review_notes = request.POST.get('notes', '')
            response.save()
            messages.success(request, 'Response rejected.')
        elif action == 'register':
            # Register student from survey response
            return redirect('admin_panel:register_from_survey', response_id=response_id)
        
        # After any action, redirect to survey responses list
        from django.urls import reverse
        url = reverse('admin_panel:survey_responses', kwargs={'survey_id': response.survey.id})
        return redirect(f"{url}?status=pending")
    
    # Get all answers with proper ordering
    answers = response.answers.all().select_related('question', 'question__section').order_by('question__section__order', 'question__order')
    
    context = {
        'response': response,
        'answers': answers,
    }
    
    return render(request, 'admin_panel/survey_response_detail.html', context)


@school_admin_required
def delete_survey_response(request, response_id):
    """Delete (move to trash) a survey response"""
    profile = request.user.profile
    response = get_object_or_404(SurveyResponse, id=response_id, survey__school=profile.school)
    
    if response.deleted_at:
        messages.warning(request, 'This response is already in trash.')
    else:
        response.soft_delete()
        messages.success(request, f'Response from {response.student_name} has been moved to trash. It will be permanently deleted after 30 days.')
    
    return redirect('admin_panel:survey_responses', survey_id=response.survey.id)


@school_admin_required
def restore_survey_response(request, response_id):
    """Restore a survey response from trash"""
    profile = request.user.profile
    response = get_object_or_404(SurveyResponse, id=response_id, survey__school=profile.school)
    
    if not response.deleted_at:
        messages.warning(request, 'This response is not in trash.')
    else:
        response.restore()
        messages.success(request, f'Response from {response.student_name} has been restored.')
    
    return redirect('admin_panel:survey_responses', survey_id=response.survey.id)


@school_admin_required
def permanently_delete_survey_response(request, response_id):
    """Permanently delete a survey response from trash - also deletes associated Student and User"""
    profile = request.user.profile
    response = get_object_or_404(SurveyResponse, id=response_id, survey__school=profile.school, deleted_at__isnull=False)
    
    survey_id = response.survey.id
    student_name = response.student_name
    
    # If student is linked, delete student and user
    if response.student:
        student = response.student
        user = student.user
        student_id = student.student_id
        
        # Delete student (this will cascade to related records)
        student.delete()
        # Delete user account
        user.delete()
        
        messages.success(request, f'Response from {student_name} (Student ID: {student_id}) and associated account have been permanently deleted.')
    else:
        messages.success(request, f'Response from {student_name} has been permanently deleted.')
    
    # Delete the response
    response.delete()
    
    return redirect('admin_panel:survey_responses', survey_id=survey_id)


@school_admin_required
def register_from_survey(request, response_id):
    """Register student from approved survey response"""
    profile = request.user.profile
    response = get_object_or_404(SurveyResponse, id=response_id, survey__school=profile.school, status='approved')
    
    if response.student:
        messages.warning(request, 'Student already registered from this response.')
        return redirect('admin_panel:survey_response_detail', response_id=response_id)
    
    if request.method == 'POST':
        # Admin may select department and program here
        dept_id = request.POST.get('department')
        prog_id = request.POST.get('program')

        # Resolve department and program safely
        department = None
        program = None
        if dept_id:
            try:
                department = Department.objects.get(id=dept_id, school=profile.school)
            except Department.DoesNotExist:
                department = None
        if prog_id:
            try:
                program = Program.objects.get(id=prog_id, department__school=profile.school)
            except Program.DoesNotExist:
                program = None

        # If department/program not provided via form, fall back to any saved values in response.additional_data
        if not department and response.additional_data:
            dept_id = response.additional_data.get('department_id')
            if dept_id:
                try:
                    department = Department.objects.get(id=dept_id, school=profile.school)
                except Department.DoesNotExist:
                    department = None
        if not program and response.additional_data:
            prog_id = response.additional_data.get('program_id')
            if prog_id:
                try:
                    program = Program.objects.get(id=prog_id, department__school=profile.school)
                except Program.DoesNotExist:
                    program = None

        # Ensure a User exists for this email (approval may have already created it)
        existing_user = User.objects.filter(username=response.student_email).first()
        temp_password = None
        created_user = False
        if existing_user:
            user = existing_user
        else:
            # Generate 8-character password and create user
            temp_password = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(8))
            user = User.objects.create(
                username=response.student_email,
                email=response.student_email,
                first_name=response.student_name.split()[0] if response.student_name.split() else '',
                last_name=' '.join(response.student_name.split()[1:]) if len(response.student_name.split()) > 1 else '',
            )
            user.set_password(temp_password)
            user.save()
            created_user = True

        # Ensure user has a profile set to student
        try:
            profile_obj = user.profile
            if profile_obj.role != 'student':
                profile_obj.role = 'student'
            if not profile_obj.school:
                profile_obj.school = profile.school
            profile_obj.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(
                user=user,
                role='student',
                school=profile.school,
                is_outsider=False
            )

        # Extract or generate student_id
        student_id = response.provided_student_id or f"S-{secrets.token_hex(4).upper()}"
        while Student.objects.filter(student_id=student_id).exists():
            student_id = f"S-{secrets.token_hex(4).upper()}"

        # Create student record
        student = Student.objects.create(
            user=user,
            student_id=student_id,
            school=profile.school,
            department=department,
            program=program,
            date_of_birth=response.additional_data.get('date_of_birth') if response.additional_data else None,
            emergency_contact_name=response.additional_data.get('emergency_contact_name', ''),
            emergency_contact_phone=response.student_phone or response.additional_data.get('emergency_contact_phone', ''),
        )

        # Link response to student and mark as registered
        response.student = student
        response.status = 'registered'
        response.save()

        # Send email with login credentials if we just created the user here
        if created_user and temp_password:
            try:
                login_url = request.build_absolute_uri('/login/')
                subject = f'Welcome to {profile.school.name} Boarding Hub System'
                message = f'''Dear {response.student_name},

Welcome to the {profile.school.name} Boarding Hub System!

Your account has been created successfully. Below are your login credentials:

Student ID: {student_id}
Email: {response.student_email}
Password: {temp_password}

IMPORTANT SECURITY NOTICE:
- Please keep this password confidential and do not share it with anyone.
- We recommend changing your password after your first login.
- Never share your login credentials with others.

You can now log in to the system using your email or student ID and the password provided above.

Login URL: {login_url}

If you have any questions or need assistance, please contact the school administration.

Best regards,
{profile.school.name} Administration Team'''

                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER)
                used_fallback, result, saved_file = send_email_with_feedback(
                    subject,
                    message,
                    from_email,
                    [response.student_email],
                )
                if used_fallback:
                    extra = f" Email content saved to: {saved_file}." if saved_file else ''
                    messages.warning(request, f'Student {student_id} registered successfully, but SMTP failed and the email was saved to sent_emails. Password: {temp_password}.{extra}')
                else:
                    messages.success(request, f'Student {student_id} registered successfully. Login credentials sent to {response.student_email}.')
            except Exception as e:
                import traceback
                print(f"Email error: {traceback.format_exc()}")
                messages.warning(request, f'Student {student_id} registered successfully, but email could not be sent. Password: {temp_password}')
        else:
            messages.success(request, f'Student {student_id} registered successfully.')

        return redirect('admin_panel:survey_response_detail', response_id=response_id)
    
    # Provide departments and programs for admin to select when registering student
    departments = Department.objects.filter(school=profile.school, is_active=True).order_by('name')
    programs = Program.objects.filter(department__school=profile.school, is_active=True).select_related('department').order_by('name')

    context = {
        'response': response,
        'departments': departments,
        'programs': programs,
    }
    
    return render(request, 'admin_panel/register_from_survey.html', context)


def setup_password(request, token):
    """Public view for students to set their password after approval"""
    from django.utils import timezone
    
    response = get_object_or_404(SurveyResponse, password_setup_token=token, status='approved')
    
    # Check if token is expired
    if response.password_setup_token_expires and response.password_setup_token_expires < timezone.now():
        messages.error(request, 'This password setup link has expired. Please contact the school administrator.')
        return render(request, 'accounts/password_setup_expired.html')
    
    # Check if already registered
    if response.student:
        messages.info(request, 'You have already set up your password. Please log in.')
        return redirect('accounts:login')
    
    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm-password', '')
        
        # Validation
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/password_setup.html', {'response': response, 'token': token})
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'accounts/password_setup.html', {'response': response, 'token': token})
        
        # Create user account
        user, created = User.objects.get_or_create(
            username=response.student_email,
            defaults={
                'email': response.student_email,
                'first_name': response.student_name.split()[0] if response.student_name.split() else '',
                'last_name': ' '.join(response.student_name.split()[1:]) if len(response.student_name.split()) > 1 else '',
            }
        )
        
        if not created:
            messages.error(request, 'This email is already registered. Please log in instead.')
            return redirect('accounts:login')
        
        # Set password
        user.set_password(password)
        user.save()
        
        # Create profile (but not student yet - will be created after profile completion)
        UserProfile.objects.create(
            user=user,
            role='student',
            school=response.survey.school,
            is_outsider=False  # School-registered student
        )
        
        # Clear token
        response.password_setup_token = None
        response.password_setup_token_expires = None
        response.save()
        
        # Log in the user
        from django.contrib.auth import login
        login(request, user)
        
        messages.success(request, 'Password set successfully! Please complete your profile to finish registration.')
        return redirect('students:complete_profile')
    
    return render(request, 'accounts/password_setup.html', {'response': response, 'token': token})


# ==================== PUBLIC SURVEY VIEW (FOR STUDENTS) ====================

def survey_take(request, unique_code):
    """Public view for students to fill out survey"""
    survey = get_object_or_404(Survey, unique_code=unique_code, status='active')
    
    # Get sections with questions
    sections = survey.sections.all().prefetch_related('questions').order_by('order')
    
    # Store survey-specific messages in context (not session)
    survey_messages = []
    
    if request.method == 'POST':
        import json
        
        # Get form data
        student_name = request.POST.get('student_name', '').strip()
        student_email = request.POST.get('student_email', '').strip().lower()
        student_phone = request.POST.get('student_phone', '').strip()
        provided_student_id = request.POST.get('student_id', '').strip()
        
        # Validate required fields (student ID also required)
        if not all([student_name, student_email, provided_student_id]):
            survey_messages.append({'type': 'error', 'message': 'Name, student ID, and university email are required.'})
            sections = survey.sections.all().prefetch_related('questions')
            return render(request, 'admin_panel/survey_take.html', {'survey': survey, 'sections': sections, 'survey_messages': survey_messages})
        
        # Basic email format check
        if '@' not in student_email:
            survey_messages.append({'type': 'error', 'message': 'Invalid email format.'})
            sections = survey.sections.all().prefetch_related('questions')
            return render(request, 'admin_panel/survey_take.html', {'survey': survey, 'sections': sections, 'survey_messages': survey_messages})
        
        # Check if email already submitted for this survey
        if SurveyResponse.objects.filter(survey=survey, student_email=student_email).exists():
            survey_messages.append({'type': 'error', 'message': 'You have already submitted a response for this survey.'})
            sections = survey.sections.all().prefetch_related('questions')
            return render(request, 'admin_panel/survey_take.html', {'survey': survey, 'sections': sections, 'survey_messages': survey_messages})
        
        # Get property owner information if required
    # property_id removed per request
        property_name = request.POST.get('property_name', '').strip()
        property_owner_name = request.POST.get('property_owner_name', '').strip()
        property_owner_phone = request.POST.get('property_owner_phone', '').strip()
        property_owner_email = request.POST.get('property_owner_email', '').strip()
        property_address = request.POST.get('property_address', '').strip()

        # Department and Program selection (explicit fields)
        department_id = request.POST.get('department', '').strip()
        program_id = request.POST.get('program', '').strip()

        if survey.require_property_info:
            # At minimum require owner email or property name
            if not any([property_owner_email, property_name]):
                survey_messages.append({'type': 'error', 'message': 'Please provide owner email or property name.'})
                sections = survey.sections.all().prefetch_related('questions')
                return render(request, 'admin_panel/survey_take.html', {'survey': survey, 'sections': sections, 'survey_messages': survey_messages})
        
        # Create survey response
        additional_data = {}
        
        # Get all answers
        answers_data = {}
        for question in SurveyQuestion.objects.filter(section__survey=survey).select_related('section'):
            answer_value = request.POST.get(f'question_{question.id}')
            
            if question.question_type == 'checkbox':
                # Multiple checkboxes
                answer_value = request.POST.getlist(f'question_{question.id}')
                if answer_value:
                    answers_data[question.id] = answer_value
            elif answer_value:
                answers_data[question.id] = answer_value
        
        # Store additional data
        additional_data['answers'] = answers_data
        if provided_student_id:
            additional_data['student_id'] = provided_student_id
        if department_id:
            try:
                additional_data['department_id'] = int(department_id)
            except (ValueError, TypeError):
                pass
        if program_id:
            try:
                additional_data['program_id'] = int(program_id)
            except (ValueError, TypeError):
                pass
        if property_owner_email:
            additional_data['property_owner_email'] = property_owner_email
        # property_id no longer stored
        if property_name:
            additional_data['property_name'] = property_name
        if property_owner_name:
            additional_data['property_owner_name'] = property_owner_name
        if property_owner_phone:
            additional_data['property_owner_phone'] = property_owner_phone
        if property_address:
            additional_data['property_address'] = property_address
        
        # Try to extract department/program from answers if available
        for q_id, answer in answers_data.items():
            question = SurveyQuestion.objects.get(id=q_id)
            if 'department' in question.text.lower() and isinstance(answer, str):
                try:
                    dept = Department.objects.filter(name__icontains=answer, school=survey.school).first()
                    if dept:
                        additional_data['department_id'] = dept.id
                except:
                    pass
            if 'program' in question.text.lower() and isinstance(answer, str):
                try:
                    prog = Program.objects.filter(name__icontains=answer, department__school=survey.school).first()
                    if prog:
                        additional_data['program_id'] = prog.id
                except:
                    pass
        
        # Create response
        response = SurveyResponse.objects.create(
            survey=survey,
            student_name=student_name,
            student_email=student_email,
            student_phone=student_phone,
            provided_student_id=provided_student_id,
            additional_data=additional_data,
            status='pending'
        )
        
        # Create answers
        for q_id, answer_value in answers_data.items():
            question = SurveyQuestion.objects.get(id=q_id)
            
            if question.question_type == 'checkbox':
                # Store as comma-separated string
                answer_choice = ', '.join(answer_value) if isinstance(answer_value, list) else answer_value
                SurveyAnswer.objects.create(
                    response=response,
                    question=question,
                    answer_choice=answer_choice
                )
            elif question.question_type == 'multiple_choice':
                SurveyAnswer.objects.create(
                    response=response,
                    question=question,
                    answer_choice=answer_value
                )
            elif question.question_type == 'rating':
                SurveyAnswer.objects.create(
                    response=response,
                    question=question,
                    answer_rating=int(answer_value) if answer_value else None
                )
            elif question.question_type == 'date':
                from datetime import datetime
                try:
                    date_obj = datetime.strptime(answer_value, '%Y-%m-%d').date()
                    SurveyAnswer.objects.create(
                        response=response,
                        question=question,
                        answer_date=date_obj
                    )
                except:
                    SurveyAnswer.objects.create(
                        response=response,
                        question=question,
                        answer_text=answer_value
                    )
            else:
                SurveyAnswer.objects.create(
                    response=response,
                    question=question,
                    answer_text=answer_value
                )
        
        # Success - redirect to success page (no messages in session)
        return render(request, 'admin_panel/survey_success.html', {'survey': survey, 'response': response})
    
    # GET request - show survey form
    sections = survey.sections.all().prefetch_related('questions')
    # Provide department/program options for the form
    departments = Department.objects.filter(school=survey.school, is_active=True).order_by('name')
    programs = Program.objects.filter(department__school=survey.school, is_active=True).select_related('department').order_by('name')

    context = {
        'survey': survey,
        'sections': sections,
        'survey_messages': survey_messages,
        'departments': departments,
        'programs': programs,
    }
    
    return render(request, 'admin_panel/survey_take.html', context)


@school_admin_required
def delete_survey(request, survey_id):
    """Delete a survey (move to trash)"""
    survey = get_object_or_404(Survey, id=survey_id, school=request.user.profile.school)
    
    if request.method == 'POST':
        from datetime import timedelta
        from django.utils import timezone
        
        # Create trash log entry
        permanent_delete_date = timezone.now() + timedelta(days=30)
        
        TrashLog.objects.create(
            school=request.user.profile.school,
            item_type='survey',
            item_id=survey.id,
            item_name=survey.title,
            item_data={
                'title': survey.title,
                'description': survey.description,
                'status': survey.status,
                'unique_code': survey.unique_code,
            },
            deleted_by=request.user,
            permanent_delete_at=permanent_delete_date,
        )
        
        # Delete the survey
        survey_title = survey.title
        survey.delete()
        
        messages.success(request, f'Survey "{survey_title}" moved to trash. It will be permanently deleted on {permanent_delete_date.strftime("%B %d, %Y")}.')
        return redirect('admin_panel:survey_list')
    
    return render(request, 'admin_panel/confirm_delete_survey.html', {'survey': survey})


@school_admin_required
def trash(request):
    """View trash with categorized deleted items"""
    profile = request.user.profile
    
    # Get trash logs (only non-permanently-deleted and not-restored)
    trash_logs = TrashLog.objects.filter(school=profile.school, is_permanently_deleted=False, restored_at__isnull=True).order_by('-deleted_at')
    
    # Filter by type if requested
    selected_type = request.GET.get('type', '')
    if selected_type:
        trash_logs = trash_logs.filter(item_type=selected_type)
    
    # Group by item type
    from itertools import groupby
    grouped_items = {}
    for item_type_val, items in groupby(trash_logs, key=lambda x: x.item_type):
        grouped_items[item_type_val] = list(items)
    
    item_types = TrashLog.ITEM_TYPES
    
    context = {
        'trash_items': trash_logs,
        'grouped_items': grouped_items,
        'item_types': item_types,
        'selected_type': selected_type,
    }
    
    return render(request, 'admin_panel/trash.html', context)





@school_admin_required
def restore_all_trash(request):
    """Restore all items in trash"""
    if request.method == 'POST':
        from django.utils import timezone
        from django.contrib.auth.models import User as DjangoUser
        trash_logs = TrashLog.objects.filter(
            school=request.user.profile.school,
            is_permanently_deleted=False,
            restored_at__isnull=True
        )

        count = trash_logs.count()

        # Attempt per-item restoration where feasible
        for item in trash_logs:
            try:
                restored = False
                data = item.item_data or {}

                if item.item_type == 'survey':
                    # Try to restore by id, otherwise recreate minimal survey from snapshot
                    if Survey.objects.filter(id=item.item_id, school=request.user.profile.school).exists():
                        Survey.objects.filter(id=item.item_id, school=request.user.profile.school).update(status=data.get('status', 'active'))
                        restored = True
                    else:
                        Survey.objects.create(
                            school=request.user.profile.school,
                            title=data.get('title', 'Restored Survey'),
                            description=data.get('description', ''),
                            status=data.get('status', 'active'),
                            unique_code=data.get('unique_code') or f"REST-{secrets.token_hex(6)}",
                        )
                        restored = True

                elif item.item_type == 'student':
                    # Try to find user by username or email and recreate Student record
                    username = data.get('username') or None
                    email = data.get('email') or None
                    user = None
                    if username:
                        user = DjangoUser.objects.filter(username=username).first()
                    if not user and email:
                        user = DjangoUser.objects.filter(email__iexact=email).first()
                    if user:
                        Student.objects.get_or_create(user=user, defaults={
                            'student_id': data.get('student_id') or f"restored-{user.id}",
                            'school': request.user.profile.school,
                            'year_level': data.get('year_level') or '',
                            'emergency_contact_name': data.get('emergency_contact_name') or '',
                            'emergency_contact_phone': data.get('emergency_contact_phone') or '',
                        })
                        restored = True

                elif item.item_type == 'user':
                    # Recreate a simple user if it does not exist
                    username = data.get('username') or data.get('email')
                    if username and not DjangoUser.objects.filter(username=username).exists():
                        DjangoUser.objects.create(
                            username=username,
                            email=data.get('email', ''),
                            first_name=data.get('first_name', ''),
                            last_name=data.get('last_name', ''),
                        )
                        restored = True

                # Mark as restored (even if underlying restoration couldn't be fully performed)
                item.restored_at = timezone.now()
                item.save()
            except Exception:
                # Ensure restored flag is still set so items won't keep showing in trash
                try:
                    item.restored_at = timezone.now()
                    item.save()
                except Exception:
                    pass

        messages.success(request, f'{count} item(s) have been restored.')
    
    return redirect('admin_panel:trash')


@school_admin_required
def delete_all_trash_permanent(request):
    """Permanently delete all items in trash"""
    if request.method == 'POST':
        trash_logs = TrashLog.objects.filter(
            school=request.user.profile.school,
            is_permanently_deleted=False
        )
        
        count = trash_logs.count()
        trash_logs.update(is_permanently_deleted=True)
        
        messages.success(request, f'{count} item(s) have been permanently deleted.')
    
    return redirect('admin_panel:trash')


@school_admin_required
def trash(request):
    """Trash management - view and restore/delete items"""
    profile = request.user.profile
    
    # Get all trash items for this school
    trash_items = TrashLog.objects.filter(
        school=profile.school,
        is_permanently_deleted=False,
        restored_at__isnull=True
    ).order_by('-deleted_at')
    
    # Filter by item type if specified
    item_type = request.GET.get('type', '')
    if item_type:
        trash_items = trash_items.filter(item_type=item_type)
    
    # Group by item type
    from itertools import groupby
    grouped_items = {}
    for item_type_val, items in groupby(trash_items, key=lambda x: x.item_type):
        grouped_items[item_type_val] = list(items)

    # Prepare item types with counts for filter UI
    item_types_with_counts = []
    for value, label in TrashLog.ITEM_TYPES:
        count = trash_items.filter(item_type=value).count()
        item_types_with_counts.append((value, label, count))

    context = {
        'trash_items': trash_items,
        'grouped_items': grouped_items,
        'item_types_with_counts': item_types_with_counts,
        'selected_type': item_type,
    }
    
    return render(request, 'admin_panel/trash.html', context)


@school_admin_required
def restore_trash_item(request, item_id):
    """Restore an item from trash"""
    profile = request.user.profile
    trash_item = get_object_or_404(TrashLog, id=item_id, school=profile.school)

    if not trash_item.can_restore():
        messages.error(request, 'This item cannot be restored.')
        return redirect('admin_panel:trash')

    # Mark as restored and attempt to restore underlying object where possible
    from django.utils import timezone
    restored = False
    trash_item.restored_at = timezone.now()
    # Attempt restoration based on item_type
    try:
        if trash_item.item_type == 'survey':
            # Surveys were soft-closed; try to reopen
            Survey.objects.filter(id=trash_item.item_id, school=profile.school).update(status=trash_item.item_data.get('status', 'active'))
            restored = True
        elif trash_item.item_type == 'student':
            # Try to recreate the Student record if missing
            data = trash_item.item_data or {}
            from django.contrib.auth.models import User as DjangoUser
            username = data.get('username')
            email = data.get('email')
            user = None
            if username:
                user = DjangoUser.objects.filter(username=username).first()
            if not user and email:
                user = DjangoUser.objects.filter(email=email).first()
            if user:
                # Create Student if not exists
                student_obj, created = Student.objects.get_or_create(user=user, defaults={
                    'student_id': data.get('student_id') or f"restored-{user.id}",
                    'school': profile.school,
                    'year_level': data.get('year_level') or '',
                    'emergency_contact_name': data.get('emergency_contact_name') or '',
                    'emergency_contact_phone': data.get('emergency_contact_phone') or '',
                })
                restored = True
        elif trash_item.item_type == 'property':
            # Property restoration may require manual steps; skip automatic for now
            restored = False
        elif trash_item.item_type == 'user':
            # Try to recreate a simple user account from snapshot
            data = trash_item.item_data or {}
            from django.contrib.auth.models import User as DjangoUser
            username = data.get('username') or data.get('email')
            if username and not DjangoUser.objects.filter(username=username).exists():
                try:
                    DjangoUser.objects.create(
                        username=username,
                        email=data.get('email', ''),
                        first_name=data.get('first_name', ''),
                        last_name=data.get('last_name', ''),
                    )
                    restored = True
                except Exception:
                    restored = False
        elif trash_item.item_type == 'response':
            # Survey responses restoration not implemented automatically
            restored = False
        elif trash_item.item_type == 'user':
            # User restoration not implemented automatically
            restored = False
    except Exception:
        restored = False

    trash_item.save()
    if restored:
        messages.success(request, f'{trash_item.item_name} has been restored.')
    else:
        messages.warning(request, f'{trash_item.item_name} marked as restored in trash. Manual restoration may be required for underlying data.')
    return redirect('admin_panel:trash')


@school_admin_required
def delete_trash_item_permanent(request, item_id):
    """Permanently delete an item from trash"""
    profile = request.user.profile
    trash_item = get_object_or_404(TrashLog, id=item_id, school=profile.school)

    if trash_item.is_permanently_deleted:
        messages.error(request, 'This item is already permanently deleted.')
        return redirect('admin_panel:trash')

    item_name = trash_item.item_name
    # Attempt to remove underlying resource
    try:
        if trash_item.item_type == 'survey':
            Survey.objects.filter(id=trash_item.item_id, school=profile.school).delete()
        elif trash_item.item_type == 'student':
            # Delete student record if exists
            Student.objects.filter(id=trash_item.item_id, school=profile.school).delete()
        elif trash_item.item_type == 'property':
            Property.objects.filter(id=trash_item.item_id, school=profile.school).delete()
        elif trash_item.item_type == 'response':
            SurveyResponse.objects.filter(id=trash_item.item_id).delete()
        elif trash_item.item_type == 'user':
            User.objects.filter(id=trash_item.item_id).delete()
    except Exception:
        # ignore errors but continue
        pass

    trash_item.is_permanently_deleted = True
    trash_item.save()

    messages.success(request, f'{item_name} has been permanently deleted.')
    return redirect('admin_panel:trash')


@school_admin_required
def delete_survey(request, survey_id):
    """Delete a survey (move to trash)"""
    profile = request.user.profile
    survey = get_object_or_404(Survey, id=survey_id, school=profile.school)
    
    if request.method == 'POST':
        # Create trash log
        from django.utils import timezone
        from datetime import timedelta
        
        TrashLog.objects.create(
            school=profile.school,
            item_type='survey',
            item_id=survey.id,
            item_name=survey.title,
            item_data={
                'title': survey.title,
                'description': survey.description,
                'status': survey.status,
                'unique_code': survey.unique_code,
            },
            deleted_by=request.user,
            permanent_delete_at=timezone.now() + timedelta(days=30)
        )
        
        # Soft delete - mark status as closed or add a deleted_at field
        survey.status = 'closed'  # Or implement soft delete with is_deleted field
        survey.save()
        
        messages.success(request, f'Survey "{survey.title}" has been moved to trash. It will be permanently deleted in 30 days.')
        return redirect('admin_panel:survey_list')
    
    context = {'survey': survey}
    return render(request, 'admin_panel/confirm_delete_survey.html', context)


@school_admin_required
def delete_student(request, student_id):
    """Delete a student (move to trash)"""
    profile = request.user.profile
    student = get_object_or_404(Student, id=student_id, school=profile.school)
    
    if request.method == 'POST':
        # Create trash log
        from django.utils import timezone
        from datetime import timedelta
        
        TrashLog.objects.create(
            school=profile.school,
            item_type='student',
            item_id=student.id,
            item_name=f"{student.user.get_full_name() or student.user.username} ({student.student_id})",
            item_data={
                'student_id': student.student_id,
                'first_name': student.user.first_name,
                'last_name': student.user.last_name,
                'email': student.user.email,
                'username': student.user.username,
                'department': student.department.code if student.department and student.department.code else (student.department.name if student.department else None),
                'program': student.program.code if student.program and student.program.code else (student.program.name if student.program else None),
                'year_level': student.year_level,
                'phone': getattr(getattr(student.user, 'profile', None), 'phone', ''),
                'emergency_contact_name': student.emergency_contact_name,
                'emergency_contact_phone': student.emergency_contact_phone,
            },
            deleted_by=request.user,
            permanent_delete_at=timezone.now() + timedelta(days=30)
        )
        
        # Delete the student (the user account will also be deleted via CASCADE or we keep it)
        student.delete()
        
        messages.success(request, f'Student "{student.user.get_full_name() or student.user.username}" has been moved to trash. It will be permanently deleted in 30 days.')
        return redirect('admin_panel:database')
    
    context = {'student': student}
    return render(request, 'admin_panel/confirm_delete_student.html', context)


@school_admin_required
def restore_all_trash(request):
    """Restore all items from trash"""
    profile = request.user.profile
    
    if request.method == 'POST':
        from django.utils import timezone
        from django.contrib.auth.models import User as DjangoUser

        trash_items = TrashLog.objects.filter(
            school=profile.school,
            is_permanently_deleted=False,
            restored_at__isnull=True
        )
        count = trash_items.count()

        for item in trash_items:
            try:
                restored = False
                data = item.item_data or {}

                if item.item_type == 'survey':
                    if Survey.objects.filter(id=item.item_id, school=profile.school).exists():
                        Survey.objects.filter(id=item.item_id, school=profile.school).update(status=data.get('status', 'active'))
                        restored = True
                    else:
                        Survey.objects.create(
                            school=profile.school,
                            title=data.get('title', 'Restored Survey'),
                            description=data.get('description', ''),
                            status=data.get('status', 'active'),
                            unique_code=data.get('unique_code') or f"REST-{secrets.token_hex(6)}",
                        )
                        restored = True

                elif item.item_type == 'student':
                    username = data.get('username') or None
                    email = data.get('email') or None
                    user = None
                    if username:
                        user = DjangoUser.objects.filter(username=username).first()
                    if not user and email:
                        user = DjangoUser.objects.filter(email__iexact=email).first()
                    if user:
                        Student.objects.get_or_create(user=user, defaults={
                            'student_id': data.get('student_id') or f"restored-{user.id}",
                            'school': profile.school,
                            'year_level': data.get('year_level') or '',
                            'emergency_contact_name': data.get('emergency_contact_name') or '',
                            'emergency_contact_phone': data.get('emergency_contact_phone') or '',
                        })
                        restored = True

                elif item.item_type == 'user':
                    username = data.get('username') or data.get('email')
                    if username and not DjangoUser.objects.filter(username=username).exists():
                        DjangoUser.objects.create(
                            username=username,
                            email=data.get('email', ''),
                            first_name=data.get('first_name', ''),
                            last_name=data.get('last_name', ''),
                        )
                        restored = True

                item.restored_at = timezone.now()
                item.save()
            except Exception:
                try:
                    item.restored_at = timezone.now()
                    item.save()
                except Exception:
                    pass

        messages.success(request, f'{count} item(s) have been restored.')
        return redirect('admin_panel:trash')
    
    return redirect('admin_panel:trash')


@school_admin_required
def delete_all_trash_permanent(request):
    """Permanently delete all items from trash"""
    profile = request.user.profile
    
    if request.method == 'POST':
        trash_items = TrashLog.objects.filter(
            school=profile.school,
            is_permanently_deleted=False
        )
        count = trash_items.count()
        
        for item in trash_items:
            item.is_permanently_deleted = True
            item.save()
        
        messages.success(request, f'{count} item(s) have been permanently deleted.')
        return redirect('admin_panel:trash')
    
    return redirect('admin_panel:trash')

