"""
Email Setup Helper Script
This script will help you set up Gmail App Password for email delivery
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_root.settings')
django.setup()

from django.conf import settings
import webbrowser

def main():
    print("=" * 70)
    print("GMAIL EMAIL SETUP HELPER")
    print("=" * 70)
    print("\nThis script will help you set up Gmail App Password for email delivery.")
    print("\n⚠️  IMPORTANT: You need to do this yourself - I cannot access your Google account.")
    print("\n" + "=" * 70)
    
    # Step 1: Check 2-Step Verification
    print("\n📋 STEP 1: Enable 2-Step Verification")
    print("-" * 70)
    print("You need to enable 2-Step Verification on your Google account first.")
    print("\nOpening: https://myaccount.google.com/security")
    input("\nPress Enter after you've enabled 2-Step Verification...")
    
    # Step 2: Generate App Password
    print("\n📋 STEP 2: Generate App Password")
    print("-" * 70)
    print("Now you'll generate an App Password for this system.")
    print("\nOpening: https://myaccount.google.com/apppasswords")
    webbrowser.open('https://myaccount.google.com/apppasswords')
    
    print("\n📝 Instructions:")
    print("1. Select 'Mail' from the 'Select app' dropdown")
    print("2. Select 'Other (Custom name)' from the 'Select device' dropdown")
    print("3. Type 'Boarding Hub System' as the name")
    print("4. Click 'Generate'")
    print("5. Copy the 16-character password (it will look like: abcd efgh ijkl mnop)")
    
    app_password = input("\n📥 Paste your 16-character App Password here (remove spaces): ").strip().replace(' ', '')
    
    if not app_password or len(app_password) != 16:
        print("\n❌ Invalid App Password! It should be exactly 16 characters.")
        print("   Please run this script again and enter the correct password.")
        return
    
    # Step 3: Update settings.py
    print("\n📋 STEP 3: Updating settings.py")
    print("-" * 70)
    
    settings_file = os.path.join(settings.BASE_DIR, 'library_root', 'settings.py')
    
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find and replace the EMAIL_HOST_PASSWORD line
        import re
        pattern = r"EMAIL_HOST_PASSWORD\s*=\s*['\"][^'\"]*['\"]"
        replacement = f"EMAIL_HOST_PASSWORD = '{app_password}'  # Gmail App Password (16 characters)"
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ Successfully updated EMAIL_HOST_PASSWORD in settings.py")
        else:
            print("⚠️  Could not find EMAIL_HOST_PASSWORD in settings.py")
            print("   Please manually update it with:")
            print(f"   EMAIL_HOST_PASSWORD = '{app_password}'")
    
    except Exception as e:
        print(f"❌ Error updating settings.py: {e}")
        print("\n   Please manually update settings.py:")
        print(f"   Find: EMAIL_HOST_PASSWORD = '...'")
        print(f"   Replace with: EMAIL_HOST_PASSWORD = '{app_password}'")
        return
    
    # Step 4: Test email
    print("\n📋 STEP 4: Test Email")
    print("-" * 70)
    print("Now let's test if the email works!")
    print("\n⚠️  IMPORTANT: You need to restart your Django server first!")
    print("   1. Stop your current server (Ctrl+C)")
    print("   2. Start it again: python manage.py runserver")
    print("   3. Then run: python test_email.py")
    
    test_now = input("\nHave you restarted the server? (y/n): ").strip().lower()
    
    if test_now == 'y':
        print("\nRunning email test...")
        os.system('python test_email.py')
    else:
        print("\n✅ Setup complete!")
        print("\n📝 Next steps:")
        print("   1. Restart your Django server")
        print("   2. Run: python test_email.py")
        print("   3. Enter your email address to test")
        print("   4. Check your inbox (and spam folder)")
    
    print("\n" + "=" * 70)
    print("Setup complete! Emails should now work.")
    print("=" * 70)

if __name__ == "__main__":
    main()

