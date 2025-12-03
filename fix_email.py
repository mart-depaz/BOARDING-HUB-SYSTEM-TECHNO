"""
Quick script to help fix email configuration
Run: python fix_email.py
"""
import os
import sys

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')

import django
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("=" * 70)
print("EMAIL CONFIGURATION TESTER")
print("=" * 70)
print(f"\nCurrent Configuration:")
print(f"  Backend: {settings.EMAIL_BACKEND}")
print(f"  Host: {settings.EMAIL_HOST}")
print(f"  Port: {settings.EMAIL_PORT}")
print(f"  User: {settings.EMAIL_HOST_USER}")
print(f"  Password: {'*' * len(settings.EMAIL_HOST_PASSWORD)}")
print(f"  From: {settings.DEFAULT_FROM_EMAIL}")

print("\n" + "=" * 70)
print("TESTING EMAIL SENDING...")
print("=" * 70)

test_email = input(f"\nEnter email to send test to (or press Enter for {settings.EMAIL_HOST_USER}): ").strip()
if not test_email:
    test_email = settings.EMAIL_HOST_USER

print(f"\nSending test email to: {test_email}")

try:
    result = send_mail(
        subject='Test Email from Boarding Hub System',
        message='This is a test email. If you receive this, your email configuration is working!',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[test_email],
        fail_silently=False,
    )
    print("\n✅ SUCCESS! Email sent via SMTP!")
    print(f"   Check {test_email} inbox (and spam folder)")
    print(f"   If you received it, your configuration is correct!")
    
except Exception as e:
    error_msg = str(e)
    error_type = type(e).__name__
    
    print(f"\n❌ ERROR: {error_type}")
    print(f"   Message: {error_msg}")
    
    if "535" in error_msg or "534" in error_msg or "authentication" in error_msg.lower():
        print("\n" + "=" * 70)
        print("🔴 AUTHENTICATION ERROR - This is the problem!")
        print("=" * 70)
        print("\nGmail requires an App Password, not your regular password.")
        print("\nTo fix this:")
        print("1. Go to: https://myaccount.google.com/apppasswords")
        print("2. Sign in with:", settings.EMAIL_HOST_USER)
        print("3. If 2-Step Verification is not enabled, enable it first")
        print("4. Generate an App Password:")
        print("   - Select 'Mail' as the app")
        print("   - Select 'Other (Custom name)' as device")
        print("   - Type: 'Boarding Hub System'")
        print("   - Click 'Generate'")
        print("5. Copy the 16-character password (no spaces)")
        print("6. Update EMAIL_HOST_PASSWORD in settings.py")
        print("7. Restart your Django server")
        print("\nThe email was saved to: library_system/sent_emails/")
        print("You can find the email content there even if SMTP fails.")
        
    elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
        print("\n🔴 CONNECTION ERROR")
        print("   Check your internet connection and firewall settings.")
    else:
        print(f"\n   Full error: {error_msg}")

print("\n" + "=" * 70)

