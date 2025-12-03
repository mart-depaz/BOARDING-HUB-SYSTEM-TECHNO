from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class School(models.Model):
    """University/College Institution"""

    name = models.CharField(max_length=200, unique=True)
    email_domain = models.CharField(
        max_length=100, blank=True, help_text="e.g., university.edu"
    )
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    facebook_url = models.URLField(
        max_length=200, blank=True, help_text="Facebook page URL for contact"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "School/University"
        verbose_name_plural = "Schools/Universities"

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Extended user profile"""

    ROLE_CHOICES = [
        ("school_admin", "School Administrator"),
        ("student", "Student"),
        ("property_owner", "Property Owner"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, null=True, blank=True, related_name="users"
    )
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", blank=True, null=True
    )
    # Boarding location fields - only for property owners to set boarding house locations
    boarding_region = models.CharField(
        max_length=100, blank=True, help_text="Region for boarding house location"
    )
    boarding_province = models.CharField(
        max_length=100, blank=True, help_text="Province for boarding house location"
    )
    boarding_city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City/Municipality for boarding house location",
    )
    boarding_barangay = models.CharField(
        max_length=100, blank=True, help_text="Barangay for boarding house location"
    )
    boarding_address = models.TextField(
        blank=True, help_text="Complete address for boarding house"
    )
    is_outsider = models.BooleanField(
        default=False,
        help_text="True if user signed up independently (not through school registration)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"

    def get_profile_photo(self):
        """Get user profile photo URL"""
        if self.profile_picture:
            return self.profile_picture.url
        return None

    def get_boarding_location(self):
        """Get formatted boarding location string"""
        parts = []
        if self.boarding_barangay:
            parts.append(f"Brgy. {self.boarding_barangay}")
        if self.boarding_city:
            parts.append(self.boarding_city)
        if self.boarding_province:
            parts.append(self.boarding_province)
        if self.boarding_region:
            parts.append(self.boarding_region)
        return ", ".join(parts) if parts else None


class Property(models.Model):
    """Boarding House/Property"""

    STATUS_CHOICES = [
        ("pending", "Pending Verification"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    ]

    property_id = models.CharField(max_length=50, unique=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_properties",
        limit_choices_to={"profile__role": "property_owner"},
    )
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="properties"
    )
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    # Property Details
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    capacity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    current_occupancy = models.PositiveIntegerField(default=0)
    monthly_rent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # Amenities
    has_wifi = models.BooleanField(default=False)
    has_kitchen = models.BooleanField(default=False)
    has_laundry = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    has_security = models.BooleanField(default=False)

    # Verification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_properties",
        limit_choices_to={"profile__role": "school_admin"},
    )
    safety_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Properties"

    def __str__(self):
        return f"{self.property_id} - {self.address}"

    @property
    def is_available(self):
        return self.current_occupancy < self.capacity and self.status == "verified"

    @property
    def availability_count(self):
        return max(0, self.capacity - self.current_occupancy)


class Department(models.Model):
    """Academic Department"""

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="departments"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(
        max_length=20, blank=True, help_text="Department code (e.g., CS, ENG)"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["school", "name"]]

    def __str__(self):
        return f"{self.name} ({self.school.name})"


class Program(models.Model):
    """Academic Program/Course"""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="programs"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True, help_text="Program code")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["department", "name"]]

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class Student(models.Model):
    """Student Profile"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    student_id = models.CharField(max_length=50, unique=True)
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    course = models.CharField(
        max_length=200, blank=True, help_text="Course/Program of study (legacy field)"
    )
    year_level = models.CharField(
        max_length=50, blank=True, help_text="e.g., 1st Year, 2nd Year"
    )
    date_of_birth = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_id"]

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name() or self.user.username}"


class BoardingAssignment(models.Model):
    """Student's boarding house assignment"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="boarding_assignments"
    )
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="assignments"
    )
    room = models.ForeignKey(
        "Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_assignments",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    agreement_signed = models.BooleanField(default=False)
    agreement_signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [["student", "property", "status"]]

    def __str__(self):
        return (
            f"{self.student.student_id} - {self.property.property_id} ({self.status})"
        )


class MaintenanceRequest(models.Model):
    """Maintenance requests from students"""

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="maintenance_requests"
    )
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="maintenance_requests"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.property.property_id}"


class PropertyReview(models.Model):
    """Student reviews/ratings for properties"""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="reviews"
    )
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [["student", "property"]]

    def __str__(self):
        return f"{self.property.property_id} - {self.rating} stars by {self.student.student_id}"


class EmergencyLog(models.Model):
    """Emergency/Incident logs"""

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    incident_id = models.CharField(max_length=50, unique=True)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="emergency_logs",
        null=True,
        blank=True,
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emergency_logs",
    )
    incident_type = models.CharField(max_length=100)
    description = models.TextField()
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.incident_id} - {self.incident_type} ({self.severity})"


class Survey(models.Model):
    """Student Registration Survey"""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
    ]

    EMAIL_VALIDATION_CHOICES = [
        ("none", "No Validation"),
        ("gmail", "Gmail Only"),
        ("university", "University Email Only"),
        ("both", "Gmail or University Email"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="surveys")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=100, blank=True, default="Student Registration"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    unique_code = models.CharField(
        max_length=50, unique=True, help_text="Unique code for survey link"
    )
    # Email validation settings
    email_validation = models.CharField(
        max_length=20,
        choices=EMAIL_VALIDATION_CHOICES,
        default="both",
        help_text="Email validation requirement for student emails",
    )
    require_property_info = models.BooleanField(
        default=True,
        help_text="Require students to provide property owner email/property information",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_surveys"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.school.name})"

    def get_shareable_link(self, request):
        """Generate shareable link for the survey"""
        return request.build_absolute_uri(f"/survey/{self.unique_code}/")


class SurveySection(models.Model):
    """Survey Sections"""

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="sections"
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(
        max_length=7, default="#818cf8", help_text="Hex color code for section styling"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.survey.title} - {self.title}"


class SurveyQuestion(models.Model):
    """Survey Questions"""

    QUESTION_TYPE_CHOICES = [
        ("text_short", "Text (Short Answer)"),
        ("text_long", "Paragraph (Long Answer)"),
        ("multiple_choice", "Multiple Choice (Single Select)"),
        ("checkbox", "Select Multiple (Checkboxes)"),
        ("rating", "Rating (1-5 Stars)"),
        ("date", "Date Picker"),
    ]

    section = models.ForeignKey(
        SurveySection, on_delete=models.CASCADE, related_name="questions"
    )
    text = models.TextField()
    question_type = models.CharField(
        max_length=20, choices=QUESTION_TYPE_CHOICES, default="text_short"
    )
    options = models.JSONField(
        default=list,
        blank=True,
        help_text="Options for multiple choice/checkbox questions",
    )
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.section.title} - {self.text[:50]}"


class SurveyResponse(models.Model):
    """Student Survey Responses"""

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("registered", "Registered"),
    ]

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="responses"
    )
    # Store student info from survey (before account creation)
    student_name = models.CharField(max_length=200)
    student_email = models.EmailField()
    student_phone = models.CharField(max_length=20, blank=True)
    provided_student_id = models.CharField(
        max_length=50, blank=True, help_text="Student ID if provided in survey"
    )
    # Additional data from survey stored as JSON
    additional_data = models.JSONField(
        default=dict, blank=True, help_text="Other survey responses"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_responses",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    # Link to student account after registration
    student = models.OneToOneField(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_response",
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True, help_text="When this response was moved to trash"
    )
    password_setup_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Token for password setup after approval",
    )
    password_setup_token_expires = models.DateTimeField(
        null=True, blank=True, help_text="Expiration time for password setup token"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [["survey", "student_email"]]

    @property
    def is_deleted(self):
        """Check if response is in trash"""
        return self.deleted_at is not None

    def soft_delete(self):
        """Move response to trash"""
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        """Restore response from trash"""
        self.deleted_at = None
        self.save()

    def __str__(self):
        return f"{self.survey.title} - {self.student_name} ({self.status})"


class SurveyAnswer(models.Model):
    """Individual answers to survey questions"""

    response = models.ForeignKey(
        SurveyResponse, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        SurveyQuestion, on_delete=models.CASCADE, related_name="answers"
    )
    answer_text = models.TextField(blank=True)
    answer_choice = models.CharField(
        max_length=200, blank=True, help_text="For multiple choice/checkbox"
    )
    answer_rating = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    answer_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["response", "question"]]

    def __str__(self):
        return f"{self.response.student_name} - {self.question.text[:50]}"


class TrashLog(models.Model):
    """Track deleted items in trash"""

    ITEM_TYPES = [
        ("survey", "Survey"),
        ("user", "User Account"),
        ("property", "Property"),
        ("student", "Student"),
        ("response", "Survey Response"),
    ]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="trash_logs"
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    item_id = models.PositiveIntegerField()  # ID of deleted item
    item_name = models.CharField(max_length=255)  # Display name
    item_data = models.JSONField(
        default=dict, blank=True
    )  # Store data for potential restoration
    deleted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="deleted_items"
    )
    deleted_at = models.DateTimeField(auto_now_add=True)
    permanent_delete_at = models.DateTimeField()  # Auto-delete after 30 days
    is_permanently_deleted = models.BooleanField(default=False)
    restored_at = models.DateTimeField(null=True, blank=True)  # When restored (if any)

    class Meta:
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"{self.item_type} - {self.item_name} (deleted {self.deleted_at.strftime('%Y-%m-%d')})"

    def can_restore(self):
        """Check if item can still be restored"""
        return not self.is_permanently_deleted

    def is_scheduled_for_deletion(self):
        """Check if item is scheduled for permanent deletion"""
        from django.utils import timezone

        return (
            not self.is_permanently_deleted
            and timezone.now() < self.permanent_delete_at
        )


class Room(models.Model):
    """Room in a property managed by the owner"""

    ROOM_TYPE_CHOICES = [
        ("single", "Single Bed"),
        ("double", "Double Bed"),
        ("twin", "Twin Bed"),
        ("deluxe", "Deluxe Suite"),
        ("family", "Family Room"),
        ("apartment", "Apartment"),
    ]

    prop = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(
        max_length=200, help_text="Room number or name (e.g., Room 101)"
    )
    room_type = models.CharField(
        max_length=50, choices=ROOM_TYPE_CHOICES, default="single"
    )
    capacity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    monthly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    description = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)
    boarding_key = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique key for students to join this room",
    )
    is_trashed = models.BooleanField(default=False, help_text="Soft delete flag")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["prop", "name"]]

    def __str__(self):
        return f"{self.prop.name} - {self.name}"

    def get_image_count(self):
        return self.images.count()


class RoomImage(models.Model):
    """Images for a room"""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="room_images/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "uploaded_at"]

    def __str__(self):
        return f"{self.room.name} - Image {self.id}"


class Conversation(models.Model):
    """Conversation between two users"""

    participant1 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversations_as_p1"
    )
    participant2 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversations_as_p2"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        # Ensure unique conversations between two users (order-independent)
        unique_together = [["participant1", "participant2"]]
        indexes = [
            models.Index(fields=["participant1", "-updated_at"]),
            models.Index(fields=["participant2", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.participant1.get_full_name() or self.participant1.username} ↔ {self.participant2.get_full_name() or self.participant2.username}"

    def get_other_user(self, user):
        """Get the other participant in the conversation"""
        return self.participant2 if user == self.participant1 else self.participant1

    def get_last_message(self):
        """Get the most recent message in this conversation"""
        return self.messages.latest("created_at") if self.messages.exists() else None

    def get_unread_count(self, user):
        """Get count of unread messages for a specific user"""
        return (
            self.messages.filter(sender__isnull=False)
            .exclude(sender=user)
            .filter(is_read=False)
            .count()
        )


class Message(models.Model):
    """Individual message in a conversation"""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
        ]

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.sender.username}: {preview}"
