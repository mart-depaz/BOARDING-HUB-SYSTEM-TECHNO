"""
Verify Gmail App Password
This script helps verify if your Gmail App Password is correct
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from django.conf import settings
import smtplib
from email.mime.text import MIMEText

def test_smtp_connection():
    """Test SMTP connection with current credentials"""
    print("=" * 70)
    print("GMAIL APP PASSWORD VERIFICATION")
    print("=" * 70)
    
    print(f"\nCurrent Configuration:")
    print(f"  EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"  EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"  EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
    print(f"  Password length: {len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 0} characters")
    
    if not settings.EMAIL_HOST_PASSWORD:
        print("\n❌ ERROR: EMAIL_HOST_PASSWORD is not set!")
        return False
    
    if len(settings.EMAIL_HOST_PASSWORD) != 16:
        print(f"\n⚠️  WARNING: Password should be exactly 16 characters, but it's {len(settings.EMAIL_HOST_PASSWORD)}")
        print("   Gmail App Passwords are always 16 characters (without spaces)")
    
    print("\n" + "=" * 70)
    print("Testing SMTP Authentication...")
    print("=" * 70)
    
    try:
        # Test SMTP connection
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
        
        print("✓ Connected to SMTP server")
        print("✓ TLS started")
        print("Attempting authentication...")
        
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        
        print("\n" + "=" * 70)
        print("✅ SUCCESS: Authentication successful!")
        print("=" * 70)
        print("Your Gmail App Password is CORRECT and working!")
        print("\nIf emails are still not being received:")
        print("  1. Check SPAM/JUNK folder")
        print("  2. Check Promotions tab (Gmail)")
        print("  3. Wait 1-5 minutes for delivery")
        print("  4. Verify recipient email address is correct")
        
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print("\n" + "=" * 70)
        print("❌ AUTHENTICATION FAILED!")
        print("=" * 70)
        print(f"Error: {str(e)}")
        print("\n🔴 Your Gmail App Password is INCORRECT or EXPIRED!")
        print("\n📋 SOLUTION:")
        print("  1. Go to: https://myaccount.google.com/apppasswords")
        print("  2. Generate a NEW App Password")
        print("     - Select 'Mail'")
        print("     - Select 'Other (Custom name)'")
        print("     - Name it 'Boarding Hub System'")
        print("  3. Copy the NEW 16-character password (remove spaces)")
        print("  4. Update EMAIL_HOST_PASSWORD in settings.py")
        print("  5. Restart Django server")
        return False
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ CONNECTION ERROR!")
        print("=" * 70)
        print(f"Error: {str(e)}")
        print("\nCheck your internet connection and firewall settings.")
        return False

if __name__ == "__main__":
    test_smtp_connection()

