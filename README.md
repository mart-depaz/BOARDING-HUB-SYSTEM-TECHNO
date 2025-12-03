# Boarding Hub System

A comprehensive Django-based platform for managing student boarding houses and property verification for universities and colleges.

## Overview

Boarding Hub is a school-managed online platform that connects students with verified boarding houses and apartments near their campus. The system ensures that all listed boarding houses meet safety and quality standards, and provides real-time tracking of where students reside.

## Features

### For School Administrators
- **Dashboard**: Real-time monitoring of student safety and property status
- **Property Audits**: Review and verify boarding houses
- **Student Management**: Track all boarding students
- **Emergency Log**: Monitor and respond to safety incidents
- **Provisioning Hub**: Register property owners and enroll students

### For Students
- **Dashboard**: View boarding assignments and applications
- **Find Housing**: Browse verified properties near campus
- **Maintenance Requests**: Submit and track maintenance issues
- **Safety Resources**: Access safety information and emergency contacts

### For Property Owners
- **Dashboard**: Manage properties and tenants
- **Tenant Management**: View active boarding assignments
- **Maintenance Center**: Handle student maintenance requests
- **Financial Reports**: Track rent and payments

## Installation

1. **Clone the repository** (or navigate to the project directory)

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create a superuser** (for Django admin access):
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

7. **Access the application**:
   - Main application: http://127.0.0.1:8000/
   - Django Admin: http://127.0.0.1:8000/admin/

## First-Time Setup

### Register School Administrator

1. Navigate to http://127.0.0.1:8000/admin-register/
2. Fill in the registration form:
   - University/College Name
   - Work Email (will be used as username)
   - Password (minimum 8 characters)
3. After registration, you can log in at http://127.0.0.1:8000/login/

**Note**: School admin registration is only available when no school administrators exist in the system.

### Adding Users

Once logged in as a school administrator:

1. Go to **Provisioning Hub** in the sidebar
2. **Register Property Owners**:
   - Enter Property ID, Owner Name, Email, and Address
   - The system will create an account for the owner
3. **Enroll Students**:
   - Enter Student ID, Name, Email
   - Optionally assign to a property
   - A temporary password will be generated (provide this securely to the student)

## User Roles

### Django Superuser
- Full access to Django admin panel
- Can manage all models and data
- Separate from school administrators
- Access: `/admin/`

### School Administrator
- Manages the school's boarding system
- Verifies properties
- Enrolls students and registers property owners
- Access: `/admin-panel/dashboard/`

### Student
- Views boarding assignments
- Searches for housing
- Submits maintenance requests
- Access: `/students/dashboard/`

### Property Owner
- Manages properties
- Views tenants
- Handles maintenance requests
- Access: `/properties/dashboard/`

## Project Structure

```
library_system/
├── accounts/          # Authentication (login, logout, registration)
├── admin_panel/       # School admin dashboard and provisioning
├── core/              # Core models (School, Property, Student, etc.)
├── properties/        # Property owner dashboard
├── students/          # Student dashboard
├── templates/          # Base templates and app-specific templates
├── static/            # Static files (CSS, JS, images)
├── media/             # User-uploaded files
└── library_root/      # Project settings and main URLs
```

## Models

### Core Models
- **School**: University/College institution
- **UserProfile**: Extended user profile with role
- **Property**: Boarding house/property
- **Student**: Student profile
- **BoardingAssignment**: Student-property relationship
- **MaintenanceRequest**: Maintenance requests from students
- **PropertyReview**: Student reviews/ratings
- **EmergencyLog**: Safety incidents and emergencies

## Security Notes

- Django admin (`/admin/`) is separate from school admin dashboard
- School administrators, students, and property owners cannot access Django admin
- Only Django superusers can access `/admin/`
- All user authentication is handled through Django's built-in auth system
- Passwords are hashed using Django's default password hashers

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Collecting Static Files
```bash
python manage.py collectstatic
```

## Technologies Used

- **Django 5.2.8**: Web framework
- **SQLite**: Database (default, can be changed to PostgreSQL/MySQL)
- **Tailwind CSS**: Styling (via CDN)
- **Python 3.x**: Programming language

## License

This project is proprietary software for educational institutions.

## Support

For issues or questions, please contact the system administrator.

