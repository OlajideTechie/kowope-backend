from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate
from .models import User, DriverProfile, otp, DriverDocument
from drf_spectacular.utils import extend_schema, OpenApiResponse
from datetime import datetime
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
