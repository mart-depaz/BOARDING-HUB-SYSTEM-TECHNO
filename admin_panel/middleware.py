"""
Middleware to protect admin panel URLs from direct access
Redirects unauthenticated users to student/owner login page
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve
from core.models import UserProfile


class AdminPanelProtectionMiddleware:
    """
    Middleware that intercepts requests to admin panel URLs
    and ensures only authenticated school admins can access them
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if the request is for an admin panel URL
        path = request.path
        
        # Exclude admin login page and survey take (public)
        excluded_paths = [
            '/admin-panel/admin-panel-portal/',
            '/survey/',
        ]
        
        # Check if this is an admin panel URL
        if path.startswith('/admin-panel/') and not any(path.startswith(excluded) for excluded in excluded_paths):
            # Check if user is authenticated
            if not request.user.is_authenticated:
                messages.info(request, 'Please log in first using the student/owner login page.')
                return redirect('accounts:login')
            
            # Check if user is a school admin
            # If authenticated and is school admin, allow access (let them type URLs directly)
            try:
                profile = request.user.profile
                if profile.role == 'school_admin':
                    # Admin is authenticated and has correct role - allow access
                    # Don't redirect, let them access the URL they typed
                    pass
                else:
                    # Authenticated but not school admin
                    messages.error(request, 'Access denied. This area is for school administrators only.')
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('accounts:login')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found. Please contact administrator.')
                from django.contrib.auth import logout
                logout(request)
                return redirect('accounts:login')
        
        response = self.get_response(request)
        return response

