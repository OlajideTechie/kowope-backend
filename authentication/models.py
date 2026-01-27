from django.db import models
import uuid

# User model
class User(models.Model):
    ROLE_CHOICES = [
        ("driver", "Driver"),
        ("agent", "Agent"),
        ("admin", "Admin"),
        ("super_admin", "Super Admin"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    phone_number = models.IntegerField(unique=True, null=False, blank=False, db_index=True)

    email = models.EmailField(unique=True, null=False, blank=False, db_index=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
     
    def __str__(self):
        return f"{self.phone_number} ({self.role})"

# Driver Profile
class DriverProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    country = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    lga = models.CharField(max_length=50)
    date_of_birth = models.DateField()

    identification = models.CharField(
        max_length=20,
        choices=[("license", "Driver License"), ("nin", "NIN")],
        null=False,
        blank=False
    )
    license_number = models.CharField(max_length=50, db_index=True)
    license_expiry_date = models.DateField()

    plate_number = models.CharField(max_length=20, db_index=True)

    pin_hash = models.CharField(max_length=128)
    verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

# Agent Profile
class AgentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agent_profile")

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    agency_name = models.CharField(max_length=100)

    location = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

# Admin Profile
class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    level = models.CharField(
        max_length=20,
        choices=[("admin", "Admin"), ("super_admin", "Super Admin")],
        default="admin"
    )
    created_at = models.DateTimeField(auto_now_add=True)
