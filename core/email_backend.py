"""
Custom email backend that tries SMTP first, then falls back to file-based storage
"""
import os
from pathlib import Path
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.core.mail.backends.filebased import EmailBackend as FileBackend
from django.conf import settings


class FallbackEmailBackend(SMTPBackend):
    """
    Email backend that tries SMTP first, and falls back to file-based storage if SMTP fails
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set up file backend as fallback
        email_dir = Path(settings.BASE_DIR) / 'sent_emails'
        os.makedirs(email_dir, exist_ok=True)
        self.file_backend = FileBackend(file_path=str(email_dir), *args, **kwargs)
    
    def send_messages(self, email_messages):
        """
        Try to send via SMTP, fall back to file if it fails
        """
        # Log recipient information
        recipients = []
        for msg in email_messages:
            recipients.extend(msg.to)
        
        print(f"\n{'='*70}")
        print(f"📧 EMAIL BACKEND: Attempting to send email")
        print(f"{'='*70}")
        print(f"Recipients: {', '.join(recipients)}")
        print(f"Backend: {self.__class__.__name__}")
        print(f"SMTP Host: {self.host}")
        print(f"SMTP Port: {self.port}")
        print(f"SMTP User: {self.username}")
        print(f"{'='*70}\n")

        try:
            # Try SMTP first
            result = super().send_messages(email_messages)
            print(f"\n{'='*70}")
            print(f"✅ SUCCESS: Email sent via SMTP")
            print(f"{'='*70}")
            print(f"Recipients: {', '.join(recipients)}")
            print(f"Number of emails sent: {result}")
            print(f"\n⚠️  IMPORTANT: If recipients don't receive emails:")
            print(f"   1. Check SPAM/JUNK folder")
            print(f"   2. Check Promotions tab (Gmail)")
            print(f"   3. Wait 1-5 minutes for delivery")
            print(f"   4. Verify email address is correct")
            print(f"{'='*70}\n")
            return result
        except Exception as e:
            # If SMTP fails, save to file
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Print detailed error information
            print("=" * 70)
            print("⚠️ SMTP EMAIL SENDING FAILED - Using file fallback")
            print("=" * 70)
            print(f"Error Type: {error_type}")
            print(f"Error Message: {error_msg}")
            
            # Check for common authentication errors
            if "535" in str(e) or "534" in str(e) or "authentication" in str(e).lower() or "invalid" in str(e).lower():
                print("\n" + "🔴" * 35)
                print("🔴 CRITICAL: AUTHENTICATION ERROR DETECTED!")
                print("🔴" * 35)
                print("\n   ❌ Gmail SMTP authentication is FAILING!")
                print("   ❌ This means emails are NOT being sent - they're being saved to files only.")
                print("\n   ✅ SOLUTION: You MUST use a Gmail App Password (not your regular password)")
                print("\n   📋 STEPS TO FIX:")
                print("   1. Enable 2-Step Verification: https://myaccount.google.com/security")
                print("   2. Generate App Password: https://myaccount.google.com/apppasswords")
                print("   3. Select 'Mail' and 'Other (Custom name)'")
                print("   4. Copy the 16-character password (remove spaces)")
                print("   5. Update EMAIL_HOST_PASSWORD in settings.py")
                print("   6. Restart Django server")
                print("\n   📖 See EMAIL_SETUP_GUIDE.md for detailed instructions")
                print("🔴" * 35 + "\n")
            elif "connection" in str(e).lower() or "timeout" in str(e).lower():
                print("\n🔴 CONNECTION ERROR DETECTED!")
                print("   Check your internet connection and firewall settings.")
            
            print(f"\n📁 FALLBACK: Saving email to file as backup")
            print(f"   Location: {self.file_backend.file_path}")
            print("=" * 70)
            
            try:
                # Mark that we used fallback for callers that inspect this backend instance
                self._used_fallback = True
                result = self.file_backend.send_messages(email_messages)
                print(f"\n✅ Email saved to file successfully")
                print(f"   Location: {self.file_backend.file_path}")
                print(f"   File name: Check the latest .log file in the folder")
                print(f"\n⚠️  ACTION REQUIRED:")
                print(f"   The email was NOT sent via SMTP (it failed).")
                print(f"   The email content has been saved to a file.")
                print(f"   You need to:")
                print(f"   1. Fix the SMTP authentication issue (likely Gmail App Password)")
                print(f"   2. Or manually send the email to: {', '.join(recipients)}")
                print(f"   3. Check the saved email file for the content")
                print("=" * 70 + "\n")
                return result
            except Exception as file_error:
                # If file backend also fails, raise the original SMTP error
                print(f"❌ Both SMTP and file backend failed!")
                raise e


def send_email_with_feedback(subject, message, from_email, recipient_list, fail_silently=False):
    """Helper to send an email using the FallbackEmailBackend and return (used_fallback, result).

    Returns:
        (used_fallback: bool, result: int)
    """
    from django.core.mail import EmailMessage

    backend = FallbackEmailBackend(
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=getattr(settings, 'EMAIL_HOST_USER', None),
        password=getattr(settings, 'EMAIL_HOST_PASSWORD', None),
        use_tls=getattr(settings, 'EMAIL_USE_TLS', False),
        use_ssl=getattr(settings, 'EMAIL_USE_SSL', False),
    )

    email = EmailMessage(subject=subject, body=message, from_email=from_email, to=recipient_list)
    result = backend.send_messages([email])
    used_fallback = getattr(backend, '_used_fallback', False)
    saved_file = None
    if used_fallback:
        # Try to locate the most recent saved email file in sent_emails
        try:
            email_dir = Path(settings.BASE_DIR) / 'sent_emails'
            files = sorted(email_dir.glob('*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                saved_file = str(files[0])
        except Exception:
            saved_file = None
    return used_fallback, result, saved_file

