from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from utils.phone import normalize_phone
from cloudinary.models import CloudinaryField


class UserManager(BaseUserManager):
    def create_user(self, email=None, password=None, **extra_fields):
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "super_admin")
        return self.create_user(email, password, **extra_fields)


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
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

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


# Agent Profile, agents are responsible for managing drivers in specific locations and providing support
class AgentStatus(models.TextChoices):
    INVITED = "invited", "Invited"

    PENDING_KYC = "pending_kyc", "Pending KYC"
    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"

class AgentProfile(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agent_profile")

    full_name = models.CharField(max_length=255, null=True, blank=True)

    area = models.ForeignKey(
        "common.Area",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agents",
    )

    status = models.CharField(
        max_length=20,
        choices=AgentStatus.choices,
        default=AgentStatus.INVITED,
        db_index=True
    )

    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_agents"
    )

    invite_token_used = models.BooleanField(default=False)

    nin_document = CloudinaryField(
        "agent_nin",
        folder="agent_documents/",
        resource_type="auto",
        type="private",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    """
    Indexes for optimizing queries on is_active field for agent profiles
    """
    class Meta:
        indexes = [
            models.Index(fields=["status"])
        ]
    def __str__(self):
        return f"Agent: {self.user.email} | {self.status}"


# Driver Profile
class DriverProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")

    agent = models.ForeignKey(
        AgentProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drivers"
    )

    full_name = models.CharField(max_length=50)

    area = models.ForeignKey(
        "common.Area",
        on_delete=models.SET_NULL,
        null=True,
        related_name="drivers"
    )
    
    phone_number = models.CharField(unique=True, max_length=15, db_index=True)

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
    Override the save method to ensure phone numbers are normalized before saving to the database
    """
    def save (self, *args, **kwargs):
        self.phone_number = normalize_phone(str(self.phone_number))
        super().save(*args, **kwargs)

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
class OTP(models.Model):
    OTP_PURPOSE_CHOICES = [
        ("signup", "Signup Verification"),
        ("login", "Login"),
        ("pin_reset", "Pin Reset"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    purpose = models.CharField(max_length=20, choices=OTP_PURPOSE_CHOICES)

    phone_number = models.CharField(max_length=15, db_index=True)
    
    code = models.CharField(max_length=6)

    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    """
    Index for optimizing queries on phone_number field for OTPs
    """
    class Meta:
        indexes = [
            models.Index(fields=["phone_number", "purpose"]),
        ]

    def has_expired(self) -> bool:
        return timezone.now() > self.expires_at



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

    def __str__(self):
        return super().__str__() + f" | Admin Level: {self.level}"



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
    
    document_file = CloudinaryField(
        "driver_document",
        folder="driver_documents/",
        resource_type="auto",
        type="private",
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

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["verified"]),
        ]

    def get_signed_url(self, expires_in=600):
        from services.document_verification_service import DocumentVerificationService

        return DocumentVerificationService.get_signed_url(
            self.document_file, expires_in=expires_in
        )
