"""
Test email sending to diagnose email delivery issues
Run this script to test if emails are being sent correctly
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
from pathlib import Path

def test_email():
    """Test sending an email"""
    print("=" * 70)
    print("EMAIL DIAGNOSTIC TEST")
    print("=" * 70)
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
    print("=" * 70)
    
    # Check sent_emails folder
    sent_emails_dir = Path(settings.BASE_DIR) / 'sent_emails'
    if sent_emails_dir.exists():
        email_files = list(sent_emails_dir.glob('*.log'))
        print(f"\n📁 Found {len(email_files)} saved email(s) in sent_emails folder")
        if email_files:
            print("   This indicates SMTP is failing and emails are being saved to files.")
            print(f"   Latest email: {max(email_files, key=lambda p: p.stat().st_mtime)}")
    else:
        print("\n📁 sent_emails folder does not exist (will be created if SMTP fails)")
    
    print("\n" + "=" * 70)
    print("ATTEMPTING TO SEND TEST EMAIL...")
    print("=" * 70)
    
    test_email_address = input("\nEnter email address to send test email to: ").strip()
    
    if not test_email_address:
        print("❌ No email address provided. Exiting.")
        return
    
    try:
        subject = "Test Email - Boarding Hub System"
        message = """This is a test email from the Boarding Hub System.

If you receive this email, it means:
✅ SMTP connection is working
✅ Email authentication is successful
✅ Email is being sent correctly

Please check:
1. Your inbox
2. Spam/Junk folder
3. Promotions tab (if using Gmail)

If you don't receive this email, check:
- The sent_emails folder for saved emails
- Console output for error messages
- Gmail App Password is correctly configured
"""
        
        print(f"\nSending test email to: {test_email_address}")
        print(f"From: {settings.DEFAULT_FROM_EMAIL}")
        print(f"Subject: {subject}")
        
        result = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [test_email_address],
            fail_silently=False,
        )
        
        print(f"\n✅ Email sending function returned: {result}")
        print("✅ If no error occurred, email should be sent!")
        print("\n⚠️  IMPORTANT: Check the console output above for any errors.")
        print("⚠️  If you see 'SMTP EMAIL SENDING FAILED', the email was saved to sent_emails folder.")
        
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR SENDING EMAIL:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"\nFull Traceback:")
        print(traceback.format_exc())
        
        if "535" in str(e) or "534" in str(e) or "authentication" in str(e).lower():
            print("\n🔴 AUTHENTICATION ERROR!")
            print("   Gmail requires an App Password, not your regular password.")
            print("   Steps to fix:")
            print("   1. Go to: https://myaccount.google.com/apppasswords")
            print("   2. Generate a new App Password for 'Mail'")
            print("   3. Copy the 16-character password")
            print("   4. Update EMAIL_HOST_PASSWORD in settings.py")
        elif "connection" in str(e).lower() or "timeout" in str(e).lower():
            print("\n🔴 CONNECTION ERROR!")
            print("   Check your internet connection and firewall settings.")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_email()
