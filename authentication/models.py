from fileinput import filename
from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
from cloudinary_storage.storage import MediaCloudinaryStorage


"""
Ensure files uploaded to Cloudinary are stored in a private folder for security and access control
"""
private_storage = MediaCloudinaryStorage(
    resource_type="raw"
)


# User model
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("driver", "Driver"),
        ("agent", "Agent"),
        ("admin", "Admin"),
        ("super_admin", "Super Admin"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=False, blank=False, db_index=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    """
    Indexes for optimizing queries on phone_number, email, and role fields
    """
    class Meta:
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
        ]
     
    """
    String representation of the user model
    """
    def __str__(self):
        return f"{self.role} | {self.phone_number or self.email}"



# Driver Profile
class DriverProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")

    full_name = models.CharField(max_length=50)

    zone = models.CharField(max_length=50)
    lga = models.CharField(max_length=50)

    phone_number = models.IntegerField(unique=True, null=False, blank=False, db_index=True)

    license_number = models.CharField(max_length=20, db_index=True)

    pin_hash = models.CharField(max_length=128)
    pin_set = models.BooleanField(default=False)

    is_phone_verified = models.BooleanField(default=False)

    verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_pin(self, raw_pin: str):
        self.pin_hash = make_password(raw_pin)
        self.pin_set = True
        self.save(update_fields=["pin_hash", "pin_set"])
    
    def check_pin(self, raw_pin: str) -> bool:
        return check_password(raw_pin, self.pin_hash)

    """
    Indexes for optimizing queries on phone_number, 
    license_number, phone_verified, and verified fields for driver profiles
    """
    class Meta:
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["license_number"]),
            models.Index(fields=["is_phone_verified"]),
            models.Index(fields=["verified"]),
        ]


# OTP model for driver phone verification and authentication
class otp(models.Model):
    OTP_PURPOSE_CHOICES = [
        ("signup", "Signup Verification"),
        ("login", "Login"),
        ("pin_reset", "Pin Reset"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    purpose = models.CharField(max_length=20, choices=OTP_PURPOSE_CHOICES)

    phone_number = models.CharField(max_length=11, db_index=True)
    
    code = models.CharField(max_length=6)

    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    """
    Set OTP expiration time to 5 minutes after creation
    """
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)
     
    def is_expired(self):
        return timezone.now() > self.expires_at

    """
    Index for optimizing queries on phone_number field for OTPs
    """
    class Meta:
        indexes = [
            models.Index(fields=["phone_number", "purpose"]),
        ]


# Agent Profile, agents are responsible for managing drivers in specific locations and providing support
class AgentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agent_profile")

    location = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    """
    Indexes for optimizing queries on is_active field for agent profiles
    """
    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
        ]



# Admin Profile mpdel for managing the system, including driver verification and overall platform administration
class AdminProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")

    level = models.CharField(
        max_length=20,
        choices=[("admin", "Admin"), ("super_admin", "Super Admin")],
        default="admin"
    )
    created_at = models.DateTimeField(auto_now_add=True)



# Driver Document model for storing driver identification documents
class DriverDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    DOCUMENT_TYPES = (
        ("nin", "NIN"),
        ("license", "Driver License"),
    )

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    def driver_doc_path(instance, filename):
        return f"driver_documents/{instance.driver.id}/{filename}"
    
    driver = models.OneToOneField(
        DriverProfile, on_delete=models.CASCADE, related_name="document"
    )

    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    
    document_file = models.FileField(
        storage=private_storage, 
        upload_to="driver_documents/"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    uploaded_by = models.ForeignKey(
        DriverProfile, on_delete=models.SET_NULL, null=True, blank=True
    )

    reviewed_by = models.ForeignKey(
        AdminProfile, on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
