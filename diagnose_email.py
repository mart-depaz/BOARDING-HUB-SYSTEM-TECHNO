"""
Email Diagnostic Tool
Run this to diagnose why emails aren't being received
Usage: python diagnose_email.py
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
from pathlib import Path

print("=" * 80)
print("EMAIL DELIVERY DIAGNOSTIC TOOL")
print("=" * 80)

# Check configuration
print("\n📋 CURRENT EMAIL CONFIGURATION:")
print("-" * 80)
print(f"  Backend: {settings.EMAIL_BACKEND}")
print(f"  Host: {settings.EMAIL_HOST}")
print(f"  Port: {settings.EMAIL_PORT}")
print(f"  Use TLS: {settings.EMAIL_USE_TLS}")
print(f"  Use SSL: {getattr(settings, 'EMAIL_USE_SSL', False)}")
print(f"  From Email: {settings.DEFAULT_FROM_EMAIL}")
print(f"  Host User: {settings.EMAIL_HOST_USER}")
print(f"  Password Length: {len(settings.EMAIL_HOST_PASSWORD)} characters")
print(f"  Password Preview: {settings.EMAIL_HOST_PASSWORD[:3]}...{settings.EMAIL_HOST_PASSWORD[-3:]}")

# Check if password looks like App Password
password = settings.EMAIL_HOST_PASSWORD
is_likely_app_password = len(password) >= 16 and (password.replace(' ', '').isalnum() or len(password.replace(' ', '')) == 16)

print("\n🔍 PASSWORD ANALYSIS:")
print("-" * 80)
if is_likely_app_password:
    print("  ✅ Password length suggests it might be an App Password")
else:
    print("  ⚠️  Password length suggests it's NOT an App Password")
    print("  ⚠️  Gmail App Passwords are 16 characters (no spaces)")
    print("  ⚠️  Regular passwords won't work with Gmail SMTP!")

# Check sent_emails folder
email_dir = Path(settings.BASE_DIR) / 'sent_emails'
print("\n📁 EMAIL BACKUP FOLDER:")
print("-" * 80)
if email_dir.exists():
    email_files = list(email_dir.glob('*.log'))
    print(f"  ✅ Folder exists: {email_dir}")
    print(f"  📧 Found {len(email_files)} saved email(s)")
    if email_files:
        latest = max(email_files, key=lambda p: p.stat().st_mtime)
        print(f"  📄 Latest email: {latest.name}")
        print(f"  ⏰ Last modified: {latest.stat().st_mtime}")
else:
    print(f"  ❌ Folder not found: {email_dir}")

# Test email sending
print("\n🧪 TESTING EMAIL SENDING:")
print("-" * 80)
test_email = input(f"\nEnter email to test (or press Enter for {settings.EMAIL_HOST_USER}): ").strip()
if not test_email:
    test_email = settings.EMAIL_HOST_USER

print(f"\nAttempting to send test email to: {test_email}")

try:
    result = send_mail(
        subject='Test Email - Boarding Hub System',
        message='This is a test email. If you receive this, your email configuration is working correctly!',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[test_email],
        fail_silently=False,
    )
    print("\n✅ SUCCESS! Email sent via SMTP!")
    print(f"   Check {test_email} inbox (and spam folder)")
    print(f"   If received: Configuration is correct!")
    print(f"   If NOT received: Check spam folder, wait 1-5 minutes, or check phone email app settings")
    
except Exception as e:
    error_msg = str(e)
    error_type = type(e).__name__
    
    print(f"\n❌ ERROR: {error_type}")
    print(f"   Message: {error_msg}")
    
    # Detailed diagnosis
    print("\n" + "=" * 80)
    print("🔴 DIAGNOSIS:")
    print("=" * 80)
    
    if "535" in error_msg or "534" in error_msg or "authentication" in error_msg.lower():
        print("\n❌ AUTHENTICATION FAILED - This is why emails aren't being received!")
        print("\n📝 SOLUTION:")
        print("   1. Go to: https://myaccount.google.com/apppasswords")
        print("   2. Sign in with:", settings.EMAIL_HOST_USER)
        print("   3. Enable 2-Step Verification if not already enabled")
        print("   4. Generate App Password:")
        print("      - Select 'Mail' as the app")
        print("      - Select 'Other (Custom name)' as device")
        print("      - Type: 'Boarding Hub System'")
        print("      - Click 'Generate'")
        print("   5. Copy the 16-character password (no spaces)")
        print("   6. Update EMAIL_HOST_PASSWORD in settings.py")
        print("   7. Restart Django server")
        print("\n   ⚠️  IMPORTANT: You MUST use App Password, not your regular Gmail password!")
        
    elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
        print("\n❌ CONNECTION FAILED")
        print("\n📝 SOLUTION:")
        print("   1. Check your internet connection")
        print("   2. Verify firewall isn't blocking port 587")
        print("   3. Try using a different network")
        
    elif "550" in error_msg or "553" in error_msg:
        print("\n❌ EMAIL ADDRESS REJECTED")
        print("\n📝 SOLUTION:")
        print("   1. Verify the recipient email address is correct")
        print("   2. Check if the email address exists")
        print("   3. Some email providers block automated emails")
        
    else:
        print(f"\n❌ UNKNOWN ERROR: {error_msg}")
        print("\n📝 SOLUTION:")
        print("   1. Check the full error message above")
        print("   2. Verify all settings in settings.py")
        print("   3. Check Django console output for more details")
    
    print("\n" + "=" * 80)
    print("📁 BACKUP SOLUTION:")
    print("=" * 80)
    print("Even if SMTP fails, all emails are saved to:")
    print(f"   {email_dir}")
    print("You can find email content (including passwords) in the saved files.")
    print("Open the .log files to see the email content.")

print("\n" + "=" * 80)
print("DIAGNOSIS COMPLETE")
print("=" * 80)

