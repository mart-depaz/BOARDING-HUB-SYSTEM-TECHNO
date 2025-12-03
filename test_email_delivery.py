"""
Test Email Delivery to Phone
This script sends a test email to verify delivery
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime

def test_email_delivery():
    print("=" * 70)
    print("EMAIL DELIVERY TEST")
    print("=" * 70)
    print(f"\nFrom: {settings.DEFAULT_FROM_EMAIL}")
    print(f"SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    recipient = input("\nEnter the phone email address to test: ").strip()
    
    if not recipient:
        print("❌ No email address provided.")
        return
    
    print(f"\n📧 Sending test email to: {recipient}")
    print("   Please wait...")
    
    try:
        subject = f"Test Email - Boarding Hub System - {datetime.now().strftime('%H:%M:%S')}"
        message = f"""This is a test email from the Boarding Hub System.

If you receive this email on your phone, email delivery is working correctly!

Test Details:
- Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- From: {settings.DEFAULT_FROM_EMAIL}
- To: {recipient}

Please check:
1. Your inbox
2. Spam/Junk folder
3. Promotions tab (if using Gmail)
4. Wait 1-5 minutes for delivery

If you don't receive this email within 5 minutes, check:
- The email address is correct
- Your phone's email app is syncing
- Spam folder settings
"""
        
        result = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        
        print("\n" + "=" * 70)
        print("✅ EMAIL SENT SUCCESSFULLY!")
        print("=" * 70)
        print(f"Result: {result} email(s) sent")
        print(f"Recipient: {recipient}")
        print(f"Time sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n📱 CHECK YOUR PHONE:")
        print("   1. Open your email app")
        print("   2. Check INBOX")
        print("   3. Check SPAM/JUNK folder")
        print("   4. Check Promotions tab (Gmail)")
        print("   5. Wait 1-5 minutes - emails can take time to arrive")
        print("   6. Pull down to refresh your inbox")
        print("\n⚠️  If you don't see the email:")
        print("   - Check spam folder carefully")
        print("   - Verify email address is correct")
        print("   - Check if phone email is syncing")
        print("   - Try checking on a computer too")
        print("=" * 70)
        
    except Exception as e:
        import traceback
        print("\n" + "=" * 70)
        print("❌ ERROR SENDING EMAIL")
        print("=" * 70)
        print(f"Error: {str(e)}")
        print(f"\nFull error:")
        print(traceback.format_exc())
        print("=" * 70)

if __name__ == "__main__":
    test_email_delivery()
