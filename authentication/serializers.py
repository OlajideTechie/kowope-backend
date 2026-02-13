from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate
from .models import DriverDocument, User, DriverProfile, OTP
from drf_spectacular.utils import extend_schema_field
from django.utils import timezone
import os

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes 

WEAK_PINS = ['1234', '0000', '1111', '2222', '3333', 
             '4444', '5555', '6666', '7777', '8888', '9999']

# User serializer for displaying user information
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'email', 'role', 'is_active', 'created_at']

# Serializer for driver signup
class DriverSignupSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)

    zone = serializers.CharField(required=True)
    lga = serializers.CharField(required=True)

    license_number = serializers.CharField(required=True)

    pin = serializers.CharField(min_length=4, max_length=4, required=True, write_only=True)

    confirm_pin = serializers.CharField(write_only=True, required=True)

    document_type = serializers.ChoiceField(choices=[("nin", "NIN"), ("license", "Driver License")])

    document_file = serializers.FileField()

    def validate_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Pin must be numeric")
        if len(value) != 4:
            raise serializers.ValidationError("Pin must be exactly 4 digits long")
        if value in WEAK_PINS:
            raise serializers.ValidationError("Pin is too weak. Please choose a stronger pin.")
        if value != self.initial_data.get("confirm_pin"):
            raise serializers.ValidationError("Pin and confirm pin do not match")
        return value

   
    def validate(self, data):

        if DriverProfile.objects.filter(license_number=data["license_number"]).exists():
            raise serializers.ValidationError("Driver with this license number already exists")

        if DriverProfile.objects.filter(phone_number=data["phone_number"].strip()).exists():
            raise serializers.ValidationError("Driver with this phone number already exists")

        if not data.get("license_number"):
            raise serializers.ValidationError("License number is required")

        if not data.get("full_name"):
            raise serializers.ValidationError("Full name is required")

        if len(data.get("full_name", "")) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters long")
        
        if not data.get("zone"):
            raise serializers.ValidationError("Zone is required")
        
        if not data.get("phone_number"):
            raise serializers.ValidationError("Phone number is required")
        
        if not data.get("document_type"):
            raise serializers.ValidationError("Document type is required")
        
        if not data.get("document_type") in ["nin", "license"]:
            raise serializers.ValidationError("Document type must be either 'nin' or 'license'")
        
        if not data.get("document_file"):
            raise serializers.ValidationError("Document file is required")
        
        if not data.get("pin"):
            raise serializers.ValidationError("Pin is required")
        
        if not data.get("confirm_pin"):
            raise serializers.ValidationError("Confirm pin is required")

        if not data.get("lga"):
            raise serializers.ValidationError("LGA is required")

        return data
    
    def validate_license_number(self, value):
        if len(value) < 7:
            raise serializers.ValidationError("License number must be at least 7 characters long")
        if not value.isalnum():
            raise serializers.ValidationError("License number must be alphanumeric")
        if not value.isupper():
            raise serializers.ValidationError("License number must be uppercase")
        return value
    
    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required")
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must be numeric")
        if len(value) != 11:
            raise serializers.ValidationError("Phone number must be 11 digits long")
        return value
    
    """ Additional validation for document file type and size """
    def validate_document_file(self, file):
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        ext = os.path.splitext(file.name)[1].lower()

        if ext not in allowed_extensions:
            raise serializers.ValidationError("Only PDF, JPG, JPEG, or PNG files are allowed.")

        blocked_mime_types = [
            'text/plain',
            'text/csv',
            'application/vnd.ms-excel',
        ]

        if file.content_type in blocked_mime_types:
            raise serializers.ValidationError("Unsupported file type. Allowed types: PDF, JPG, JPEG, PNG")

        if file.size > MAX_FILE_SIZE:  # Limit file size to 5MB
            raise serializers.ValidationError("Document file size should not exceed 5MB")
        
        return file
    
    # Additional validation for pin strength and matching
    def validate_empty_values(self, data):
        return super().validate_empty_values(data)
    

    """
    Create a new driver profile
    """
    def create(self, validated_data):
        # pin = validated_data.pop("pin")

        user = User.objects.create(
            phone_number=validated_data["phone_number"],
            role="driver"
        )

        DriverProfile.objects.create(
            user=user,
            pin_hash=make_password(validated_data.pop("pin")),
            **validated_data
        )

        return user
    

class DriverLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    pin = serializers.CharField()

    def validate(self, data):
        user = User.objects.filter(
            phone_number=data["phone_number"],
            role="driver"
        ).first()

        if not user:
            raise serializers.ValidationError("Invalid credentials provided")

        driver = user.driver_profile
        if not check_password(data["pin"], driver.pin_hash):
            raise serializers.ValidationError("Invalid credentials provided")

        return user


class StaffSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8)

    def create(self, validated_data):
        user = User.objects.create(
            email=validated_data["email"],
            role="staff"
        )
        user.set_password(validated_data["password"])
        user.save()
        return user

class StaffLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(
            email=data["email"],
            password=data["password"]
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials provided")

        return user


class DriverLogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, data):
        if not data.get("refresh_token"):
            raise serializers.ValidationError("Refresh token is required")
        if not isinstance(data["refresh_token"], str):
            raise serializers.ValidationError("Refresh token must be a string")
        if len(data["refresh_token"].strip()) == 0:
            raise serializers.ValidationError("Refresh token cannot be empty")
        if len(data["refresh_token"]) > 500:
            raise serializers.ValidationError("Refresh token is too long")
        if len(data["refresh_token"]) < 10:
            raise serializers.ValidationError("Refresh token is too short")
        if not data["refresh_token"].startswith("eyJ"):  # Basic check for JWT format
            raise serializers.ValidationError("Invalid refresh token format")
        if " " in data["refresh_token"]:
            raise serializers.ValidationError("Refresh token cannot contain spaces")
        if not all(c.isalnum() or c in ['.', '_', '-'] for c in data["refresh"]):
            raise serializers.ValidationError("Refresh token contains invalid characters")
        return data
    

class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required")
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must be numeric")
        if len(value) != 11:
             raise serializers.ValidationError("Phone number must be 11 digits long")
        return value
    
    def validate_code(self, value):
        if not value:
            raise serializers.ValidationError("OTP code is required")
        if not value.isdigit():
            raise serializers.ValidationError("OTP code must be numeric")
        if len(value) != 6:
            raise serializers.ValidationError("OTP code must be 6 digits long")
        if value == "000000":
            raise serializers.ValidationError("OTP code cannot be all zeros")
        
        return value
    

class ResendOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required")


class ChangePinSerializer(serializers.Serializer):
    old_pin = serializers.CharField(min_length=4, max_length=4)
    new_pin = serializers.CharField(min_length=4, max_length=4)

    def validate_old_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Old pin must be numeric")
        if len(value) != 4:
            raise serializers.ValidationError("Old pin must be exactly 4 digits long")
        return value

    def validate_new_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("New pin must be numeric")
        if len(value) != 4:
            raise serializers.ValidationError("New pin must be exactly 4 digits long")
        if value in WEAK_PINS:
            raise serializers.ValidationError("New pin is too weak. Please choose a stronger pin.")
        if value == self.initial_data.get("old_pin"):
            raise serializers.ValidationError("New pin cannot be the same as old pin")
        return value
    

class ResetPinSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()
    new_pin = serializers.CharField(min_length=4, max_length=4)

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required")
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must be numeric")
        if len(value) != 11:
             raise serializers.ValidationError("Phone number must be 11 digits long")
        return value

    def validate_code(self, value):
        if not value:
            raise serializers.ValidationError("OTP code is required")
        if not value.isdigit():
            raise serializers.ValidationError("OTP code must be numeric")
        if len(value) != 6:
            raise serializers.ValidationError("OTP code must be 6 digits long")
        if value == "000000":
            raise serializers.ValidationError("OTP code cannot be all zeros")
        
        otp = OTP.objects.filter(code=value).first()
        if otp is None:
            raise serializers.ValidationError("Invalid OTP code")
        if otp.is_used:
            raise serializers.ValidationError("OTP code has already been used")
        if otp.expires_at < timezone.now():
            raise serializers.ValidationError("OTP code has expired")
        return value

    def validate_new_pin(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("New pin must be numeric")
        if len(value) != 4:
            raise serializers.ValidationError("New pin must be exactly 4 digits long")
        if value in WEAK_PINS:
            raise serializers.ValidationError("New pin is too weak. Please choose a stronger pin.")
        return value
    


class DriverDocumentSerializer(serializers.ModelSerializer):
    document_file = serializers.SerializerMethodField()

    class Meta:
        model = DriverDocument
        fields = ['document_type', 'document_file', 'status']
    
    @extend_schema_field(serializers.URLField())
    def get_document_file(self, obj):
        request = self.context.get('request')
        if obj.document_file and hasattr(obj.document_file, 'url'):
            return request.build_absolute_uri(obj.document_file.url)
        return None


class DriverProfileSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="user.id", read_only=True)
    phone_number = serializers.CharField(source="user.phone_number", read_only=True)
    is_phone_verified = serializers.BooleanField(source="user.is_phone_verified", read_only=True)
    verified = serializers.BooleanField(source="user.verified", read_only=True)
    created_at = serializers.DateTimeField(source="user.created_at", read_only=True)
    documents = DriverDocumentSerializer(source="document")

    class Meta:
        model = DriverProfile
        fields = [
            'id', 
            'full_name', 
            'phone_number', 
            'license_number', 
            'is_phone_verified', 
            'verified', 
            'documents',
            'created_at',
            ]