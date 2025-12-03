import json
import random
import re
import string
from datetime import timedelta
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from core.models import Property, School, Student, UserProfile

from .models import PasswordResetSession

RESET_CODE_TTL_MINUTES = 10
MAX_VERIFICATION_ATTEMPTS = 5


def _build_portal_context(
    mode='signup',
    role='student',
    login_email='',
    student_prefill=None,
    owner_prefill=None,
    auto_select_role=False,
):
    """Helper to centralize initial state + prefill data for the access portal."""
    valid_modes = {'login', 'signup'}
    valid_roles = {'student', 'owner'}
    normalized_mode = mode if mode in valid_modes else 'signup'
    normalized_role = role if role in valid_roles else 'student'

    default_student = {
        'fullName': '',
        'email': '',
        'phone': '',
        'school': '',
    }
    default_owner = {
        'fullName': '',
        'email': '',
        'phone': '',
        'companyName': '',
    }

    if student_prefill:
        default_student.update(student_prefill)
    if owner_prefill:
        default_owner.update(owner_prefill)

    portal_prefill = {
        'login': {'email': login_email},
        'student': default_student,
        'owner': default_owner,
    }

    return {
        'initial_mode': normalized_mode,
        'initial_role': normalized_role,
        'auto_select_role': auto_select_role,
        'portal_prefill': json.dumps(portal_prefill),
    }


def _normalize_phone_number(value):
    """Convert any phone-like input into a standard 11-digit PH mobile number."""
    if not value:
        return ''

    digits = re.sub(r'\D', '', value)
    if digits.startswith('63'):
        digits = '0' + digits[2:]
    elif digits.startswith('9') and len(digits) == 10:
        digits = '0' + digits
    elif digits.startswith('00963'):
        digits = '0' + digits[5:]

    if len(digits) > 11:
        digits = digits[-11:]

    if len(digits) == 10:
        digits = '0' + digits

    if len(digits) == 11 and digits.startswith('0'):
        return digits
    return digits


def _generate_reset_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


def _send_reset_code(user, code):
    subject = "Boarding Hub System Access Code"
    message = (
        "Greetings from Boarding Hub System.\n\n"
        f"Use the following one-time access code to reset your password: {code}\n"
        "This code is valid for the next 10 minutes. If you did not request this, "
        "you can safely ignore this email.\n\n"
        "— Boarding Hub Security Team"
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@boardinghub.local'
    send_mail(subject, message, from_email, [user.email])


def _resolve_username_by_identifier(identifier, selected_role):
    """Map any identifier (email, phone, student id, property id) to a login username."""
    if not identifier:
        return ''

    identifier = identifier.strip()
    normalized_phone = _normalize_phone_number(identifier)

    if '@' in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
        if user:
            return user.username

    if selected_role == 'student':
        student = Student.objects.select_related('user').filter(student_id__iexact=identifier).first()
        if student:
            return student.user.username

        phone_filters = []
        if normalized_phone:
            phone_filters.append(Q(phone__iexact=normalized_phone))
        if normalized_phone and normalized_phone != identifier:
            phone_filters.append(Q(phone__iexact=identifier))
        elif not normalized_phone and identifier:
            phone_filters.append(Q(phone__iexact=identifier))
        phone_query = Q()
        for clause in phone_filters:
            phone_query |= clause
        profile = (
            UserProfile.objects.select_related('user')
            .filter(role='student')
            .filter(phone_query)
            .first()
            if phone_filters
            else None
        )
        if profile:
            return profile.user.username
    else:
        phone_filters = []
        if normalized_phone:
            phone_filters.append(Q(phone__iexact=normalized_phone))
        if normalized_phone and normalized_phone != identifier:
            phone_filters.append(Q(phone__iexact=identifier))
        elif not normalized_phone and identifier:
            phone_filters.append(Q(phone__iexact=identifier))
        phone_query = Q()
        for clause in phone_filters:
            phone_query |= clause
        profile = (
            UserProfile.objects.select_related('user')
            .filter(role='property_owner')
            .filter(phone_query)
            .first()
            if phone_filters
            else None
        )
        if profile:
            return profile.user.username

        property_obj = Property.objects.select_related('owner').filter(property_id__iexact=identifier).first()
        if property_obj:
            return property_obj.owner.username

    fallback_user = User.objects.filter(username__iexact=identifier).first()
    if fallback_user:
        return fallback_user.username

    return identifier


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Login page for students and property owners only (NOT school admins)"""
    
    # IMPORTANT: Handle GET requests first - just show the login page for all GET requests
    if request.method == 'GET':
        # If user has a session but we're at the login page, they might have an invalid session
        # Clear it to prevent redirect loops
        if request.user.is_authenticated:
            logout(request)
        
        role_param = request.GET.get('role')
        mode_param = request.GET.get('mode')
        valid_roles = {'student', 'owner'}
        valid_modes = {'login', 'signup'}
        initial_role = role_param if role_param in valid_roles else 'student'
        initial_mode = mode_param if mode_param in valid_modes else 'login'
        auto_select_role = role_param in valid_roles
        
        context = _build_portal_context(
            mode=initial_mode,
            role=initial_role,
            auto_select_role=auto_select_role,
        )
        return render(request, 'accounts/login.html', context)
    
    # POST requests: Handle authentication
    role_param = request.GET.get('role')
    mode_param = request.GET.get('mode')
    valid_roles = {'student', 'owner'}
    valid_modes = {'login', 'signup'}
    initial_role = role_param if role_param in valid_roles else 'student'
    initial_mode = mode_param if mode_param in valid_modes else 'login'
    auto_select_role = role_param in valid_roles
    
    if request.method == 'POST':
        email_or_id = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        selected_role = request.POST.get('selected-role', initial_role)
        if selected_role not in valid_roles:
            selected_role = 'student'

        # Resolve identifier into a canonical username based on selected role
        username = _resolve_username_by_identifier(email_or_id, selected_role)

        # Try to authenticate with email/username
        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                profile = user.profile
                # Prevent school_admins from using the main login page
                if profile.role == 'school_admin':
                    messages.error(request, 'School administrators must use the Admin Panel Portal.')
                    return render(request, 'accounts/login.html')

                role_map = {
                    'student': 'student',
                    'owner': 'property_owner',
                }
                expected_role = role_map.get(selected_role, 'student')
                if profile.role != expected_role:
                    expected_label = 'Student' if expected_role == 'student' else 'Property Owner'
                    messages.error(
                        request,
                        f"This account is registered as {expected_label}. Please switch to the {expected_label} portal before logging in."
                    )
                    context = _build_portal_context(
                        mode='login',
                        role=selected_role,
                        login_email=email_or_id,
                        auto_select_role=True,
                    )
                    return render(request, 'accounts/login.html', context)

                # Login any non-admin user (students and property owners)
                login(request, user)
                return redirect('accounts:redirect_after_login')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found. Please contact administrator.')
        else:
            messages.error(request, 'Invalid email or password.')
        context = _build_portal_context(
            mode='login',
            role=selected_role,
            login_email=email_or_id,
            auto_select_role=True,
        )
        return render(request, 'accounts/login.html', context)


@require_http_methods(["POST"])
def password_reset_request(request):
    """Start the OTP flow by sending a code to the user's email."""
    email = request.POST.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'success': False, 'message': 'Email is required.'}, status=400)

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return JsonResponse({'success': False, 'message': 'No account found for that email.'}, status=404)

    code = _generate_reset_code()
    expires_at = timezone.now() + timedelta(minutes=RESET_CODE_TTL_MINUTES)
    session = PasswordResetSession.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=expires_at,
    )

    try:
        _send_reset_code(user, code)
    except Exception:
        session.delete()
        return JsonResponse({'success': False, 'message': 'Unable to dispatch access code. Please try again.'}, status=500)

    return JsonResponse({
        'success': True,
        'requestId': str(session.request_id),
        'message': 'Access code sent. Please check your inbox.',
    })


@require_http_methods(["POST"])
def password_reset_verify(request):
    """Verify the OTP code before letting the user set a new password."""
    request_id = request.POST.get('requestId', '').strip()
    code = request.POST.get('code', '').strip()

    if not request_id or not code:
        return JsonResponse({'success': False, 'message': 'Code verification requires all fields.'}, status=400)

    session = PasswordResetSession.objects.select_related('user').filter(request_id=request_id, used_at__isnull=True).first()
    if not session:
        return JsonResponse({'success': False, 'message': 'Reset request not found or already used.'}, status=404)

    if session.expires_at < timezone.now():
        return JsonResponse({'success': False, 'message': 'This access code has expired.'}, status=410)

    if session.attempts >= MAX_VERIFICATION_ATTEMPTS:
        return JsonResponse({'success': False, 'message': 'Too many failed attempts. Request a new code.'}, status=429)

    if not check_password(code, session.code_hash):
        session.attempts += 1
        session.save(update_fields=['attempts'])
        return JsonResponse({'success': False, 'message': 'Invalid access code.'}, status=400)

    if not session.verified_at:
        session.verified_at = timezone.now()
        session.save(update_fields=['verified_at'])

    return JsonResponse({'success': True, 'message': 'Access code verified.'})


@require_http_methods(["POST"])
def password_reset_complete(request):
    """Finalize the reset by setting a new password."""
    request_id = request.POST.get('requestId', '').strip()
    code = request.POST.get('code', '').strip()
    password = request.POST.get('password', '')
    confirm = request.POST.get('confirmPassword', '')

    if not all([request_id, code, password, confirm]):
        return JsonResponse({'success': False, 'message': 'All fields are required.'}, status=400)

    if password != confirm:
        return JsonResponse({'success': False, 'message': 'Passwords do not match.'}, status=400)

    if len(password) < 8:
        return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters.'}, status=400)

    session = PasswordResetSession.objects.select_related('user').filter(request_id=request_id, used_at__isnull=True).first()
    if not session:
        return JsonResponse({'success': False, 'message': 'Reset request not found or already used.'}, status=404)

    if session.expires_at < timezone.now():
        return JsonResponse({'success': False, 'message': 'This access code has expired.'}, status=410)

    if not check_password(code, session.code_hash):
        return JsonResponse({'success': False, 'message': 'Invalid access code.'}, status=400)

    user = session.user
    user.set_password(password)
    user.save(update_fields=['password'])

    session.mark_used()

    return JsonResponse({'success': True, 'message': 'Password updated. You can log in with your new access key.'})


@login_required
def redirect_after_login(request):
    """Redirect users to their appropriate dashboard based on role"""
    try:
        profile = request.user.profile
        if profile.role == 'school_admin':
            # School admins should go to admin dashboard directly
            return redirect('admin_panel:dashboard')
        elif profile.role == 'student':
            return redirect('students:student_dashboard')
        elif profile.role == 'property_owner':
            return redirect('properties:owner_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found. Please contact administrator.')
        logout(request)
        return redirect('accounts:login')
    
    messages.error(request, 'Unknown user role.')
    logout(request)
    return redirect('accounts:login')


@require_http_methods(["GET", "POST"])
def admin_registration(request):
    """School admin registration - accessible via URL"""
    # If user is already authenticated, redirect them appropriately
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'school_admin':
                return redirect('admin_panel:dashboard')
            else:
                return redirect('accounts:redirect_after_login')
        except UserProfile.DoesNotExist:
            pass
    
    if request.method == 'POST':
        org_name = request.POST.get('org-name', '').strip()
        admin_email = request.POST.get('admin-email', '').strip()
        password = request.POST.get('admin-password', '')
        confirm_password = request.POST.get('confirm-password', '')
        
        # Validation
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/admin_registration.html', {
                'org_name': org_name,
                'admin_email': admin_email
            })
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'accounts/admin_registration.html', {
                'org_name': org_name,
                'admin_email': admin_email
            })
        
        # Create school
        school, created = School.objects.get_or_create(name=org_name)
        
        if User.objects.filter(username=admin_email).exists():
            messages.error(request, 'This email is already registered.')
            return render(request, 'accounts/admin_registration.html', {
                'org_name': org_name,
                'admin_email': admin_email
            })
        
        user = User.objects.create_user(
            username=admin_email,
            email=admin_email,
            password=password
        )
        
        # Create profile
        UserProfile.objects.create(
            user=user,
            role='school_admin',
            school=school
        )
        
        # Automatically log in the user and redirect to dashboard
        login(request, user)
        messages.success(request, f'Admin account created for {org_name}. Welcome to your dashboard!')
        return redirect('admin_panel:dashboard')
    
    return render(request, 'accounts/admin_registration.html')


@require_http_methods(["GET", "POST"])
def student_signup(request):
    """Student signup for outsider users (independent registration)"""
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'student':
                return redirect('students:student_dashboard')
            else:
                return redirect('accounts:redirect_after_login')
        except UserProfile.DoesNotExist:
            pass
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm-password', '')
        first_name = request.POST.get('first-name', '').strip()
        last_name = request.POST.get('last-name', '').strip()
        full_name = request.POST.get('full-name', '').strip()
        phone = request.POST.get('phone', '').strip()
        normalized_phone = _normalize_phone_number(phone)
        if phone and (len(normalized_phone) != 11):
            messages.error(request, 'Phone numbers must be 11-digit Philippine numbers (e.g., 09171234567).')
            context = _build_portal_context(
                mode='signup',
                role='student',
                auto_select_role=True,
                student_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'school': school,
                },
            )
            return render(request, 'accounts/student_signup.html', context)
        school = request.POST.get('school', '').strip()

        if (not first_name and not last_name) and full_name:
            parts = full_name.split()
            if parts:
                first_name = parts[0]
                last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        # Validation
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            context = _build_portal_context(
                mode='signup',
                role='student',
                auto_select_role=True,
                student_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'school': school,
                },
            )
            return render(request, 'accounts/student_signup.html', context)
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            context = _build_portal_context(
                mode='signup',
                role='student',
                auto_select_role=True,
                student_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'school': school,
                },
            )
            return render(request, 'accounts/student_signup.html', context)
        
        if not email:
            messages.error(request, 'Email is required.')
            context = _build_portal_context(
                mode='signup',
                role='student',
                auto_select_role=True,
            )
            return render(request, 'accounts/student_signup.html', context)
        
        if User.objects.filter(username=email).exists():
            messages.error(request, 'This email is already registered. Please log in instead.')
            context = _build_portal_context(
                mode='signup',
                role='student',
                auto_select_role=True,
                student_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': phone,
                    'school': school,
                },
            )
            return render(request, 'accounts/student_signup.html', context)
        
        # Check if phone is already registered (if provided)
        if normalized_phone and UserProfile.objects.filter(phone=normalized_phone).exists():
            messages.error(request, 'This phone number is already registered. Please use a different number.')
            context = _build_portal_context(
                mode='signup',
                role='student',
                auto_select_role=True,
                student_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'school': school,
                },
            )
            return render(request, 'accounts/student_signup.html', context)
        
        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create profile as outsider
        UserProfile.objects.create(
            user=user,
            role='student',
            phone=normalized_phone or '',
            is_outsider=True,
            school=None  # Outsider users don't belong to a school
        )
        
        # Create a placeholder Student profile with temporary student_id
        # This allows the student to access their dashboard immediately
        # They'll complete their profile later
        from core.models import Student
        import uuid
        
        # Generate temporary unique student_id
        temp_student_id = f"TEMP-{secrets.token_hex(4).upper()}"
        while Student.objects.filter(student_id=temp_student_id).exists():
            temp_student_id = f"TEMP-{secrets.token_hex(4).upper()}"
        
        # Create Student profile with temporary values
        # No school assigned yet (outsider student)
        Student.objects.create(
            user=user,
            student_id=temp_student_id,
            school=None  # Will be set when they complete their profile
        )
        
        # Automatically log in the user
        login(request, user)
        messages.success(request, 'Account created successfully! Welcome to Boarding Hub.')
        return redirect('students:student_dashboard')
    
    context = _build_portal_context(
        mode='signup',
        role='student',
        auto_select_role=True,
    )
    return render(request, 'accounts/student_signup.html', context)


@require_http_methods(["GET", "POST"])
def property_owner_signup(request):
    """Property owner signup for outsider users (independent registration)"""
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'property_owner':
                return redirect('properties:owner_dashboard')
            else:
                return redirect('accounts:redirect_after_login')
        except UserProfile.DoesNotExist:
            pass
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm-password', '')
        first_name = request.POST.get('first-name', '').strip()
        last_name = request.POST.get('last-name', '').strip()
        full_name = request.POST.get('full-name', '').strip()
        phone = request.POST.get('phone', '').strip()
        company_name = request.POST.get('company-name', '').strip()
        normalized_phone = _normalize_phone_number(phone)

        if (not first_name and not last_name) and full_name:
            parts = full_name.split()
            if parts:
                first_name = parts[0]
                last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        # Validation
        if not normalized_phone or len(normalized_phone) != 11:
            messages.error(request, 'Please provide an 11-digit Philippine contact number (ex: 09171234567).')
            context = _build_portal_context(
                mode='signup',
                role='owner',
                auto_select_role=True,
                owner_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'companyName': company_name,
                },
            )
            return render(request, 'accounts/property_owner_signup.html', context)
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            context = _build_portal_context(
                mode='signup',
                role='owner',
                auto_select_role=True,
                owner_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'companyName': company_name,
                },
            )
            return render(request, 'accounts/property_owner_signup.html', context)
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            context = _build_portal_context(
                mode='signup',
                role='owner',
                auto_select_role=True,
                owner_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'companyName': company_name,
                },
            )
            return render(request, 'accounts/property_owner_signup.html', context)
        
        if not email:
            messages.error(request, 'Email is required.')
            context = _build_portal_context(
                mode='signup',
                role='owner',
                auto_select_role=True,
            )
            return render(request, 'accounts/property_owner_signup.html', context)
        
        if User.objects.filter(username=email).exists():
            messages.error(request, 'This email is already registered. Please log in instead.')
            context = _build_portal_context(
                mode='signup',
                role='owner',
                auto_select_role=True,
                owner_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': phone,
                    'companyName': company_name,
                },
            )
            return render(request, 'accounts/property_owner_signup.html', context)
        
        # Check if phone is already registered (if provided)
        if normalized_phone and UserProfile.objects.filter(phone=normalized_phone).exists():
            messages.error(request, 'This phone number is already registered. Please use a different number.')
            context = _build_portal_context(
                mode='signup',
                role='owner',
                auto_select_role=True,
                owner_prefill={
                    'fullName': full_name or f'{first_name} {last_name}'.strip(),
                    'email': email,
                    'phone': normalized_phone or phone,
                    'companyName': company_name,
                },
            )
            return render(request, 'accounts/property_owner_signup.html', context)
        
        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create profile as outsider
        UserProfile.objects.create(
            user=user,
            role='property_owner',
            phone=normalized_phone,
            is_outsider=True,
            school=None  # Outsider users don't belong to a school
        )
        
        # Auto-generate a Property for this owner so they have a property_id available
        try:
            from core.models import Property, School
        except Exception:
            Property = None
            School = None

        def _generate_unique_property_id():
            import uuid
            for _ in range(10):
                pid = f"BH-{uuid.uuid4().hex[:8].upper()}"
                if not Property.objects.filter(property_id=pid).exists():
                    return pid
            # Fallback using timestamp
            import time
            return f"BH-{int(time.time())}"

        if Property is not None:
            try:
                pid = _generate_unique_property_id()
                # Try to find a sensible School to attach; fall back to creating a placeholder
                school = None
                try:
                    school = School.objects.first()
                except Exception:
                    school = None

                if not school:
                    # create a placeholder school so FK constraints are satisfied
                    school = School.objects.create(name='Unassigned School')

                # Use company_name or a placeholder address/name
                addr = company_name if company_name else f"Owner {user.username} property"
                prop_name = company_name or f"{user.get_full_name() or user.username} Property"

                Property.objects.create(
                    property_id=pid,
                    owner=user,
                    school=school,
                    address=addr,
                    name=prop_name
                )
            except Exception as e:
                # Don't fail signup if property creation fails; log to console
                import logging
                logging.getLogger(__name__).exception('Failed to auto-create Property for new owner: %s', e)
        
        # Automatically log in the user
        login(request, user)
        messages.success(request, 'Account created successfully! Welcome to Boarding Hub.')
        return redirect('properties:owner_dashboard')
    
    context = _build_portal_context(
        mode='signup',
        role='owner',
        auto_select_role=True,
    )
    return render(request, 'accounts/property_owner_signup.html', context)


@login_required
def logout_view(request):
    """Logout view"""
    # Check role before logout to redirect appropriately
    try:
        profile = request.user.profile
        is_school_admin = profile.role == 'school_admin'
    except UserProfile.DoesNotExist:
        is_school_admin = False
    
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    
    # Redirect school admins to admin portal, others to regular login
    if is_school_admin:
        return redirect('admin_panel:admin_login')
    return redirect('accounts:login')
