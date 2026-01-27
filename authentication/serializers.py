from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate
from .models import User, DriverProfile

# User serializer for displaying user information
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'phone_number', 'email', 'role', 'is_active', 'created_at']

# Serializer for driver signup
class DriverSignupSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    pin = serializers.CharField(min_length=4, max_length=4)
    confirm_pin = serializers.CharField(min_length=4, max_length=4)

    first_name = serializers.CharField()
    last_name = serializers.CharField()
    country = serializers.CharField()
    state = serializers.CharField()
    lga = serializers.CharField()
    date_of_birth = serializers.DateField()

    license_number = serializers.CharField()
    license_expiry_date = serializers.DateField()
    plate_number = serializers.CharField()

    def validate(self, data):
        if data["pin"] != data["confirm_pin"]:
            raise serializers.ValidationError("PINs do not match")

        if DriverProfile.objects.filter(license_number=data["license_number"]).exists():
            raise serializers.ValidationError("Driver with this license number already exists")

        if DriverProfile.objects.filter(phone_number=data["phone_number"]).exists():
            raise serializers.ValidationError("Driver with this phone number already exists")

        if DriverProfile.objects.filter(plate_number=data["plate_number"]).exists():
            raise serializers.ValidationError("Driver with this plate number already exists")

        if not data.get("identification"):
            raise serializers.ValidationError("Identification is required")

        if not data.get("license_number"):
            raise serializers.ValidationError("License number is required")

        if not data.get("license_expiry_date"):
            raise serializers.ValidationError("License expiry date is required")

        if not data.get("plate_number"):
            raise serializers.ValidationError("Plate number is required")

        if not data.get("first_name"):
            raise serializers.ValidationError("First name is required")

        if not data.get("last_name"):
            raise serializers.ValidationError("Last name is required")

        if len(data.get("first_name", "")) < 2:
            raise serializers.ValidationError("First name must be at least 2 characters long")

        if not data.get("country"):
            raise serializers.ValidationError("Country is required")

        if not data.get("state"):
            raise serializers.ValidationError("State is required")

        if not data.get("lga"):
            raise serializers.ValidationError("LGA is required")

        return data
    
    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required")
        if not value.isdigit():
            raise serializers.ValidationError("Phone number must be numeric")
        if len(value) != 11:
            raise serializers.ValidationError("Phone number must be 11 digits long")
        return value

    """
    Validate driver's date of birth
    """
    def validate_date_of_birth(self, value):
        if not value:
            raise serializers.ValidationError("Date of birth is required")

        if not self.is_valid_date(value):
            raise serializers.ValidationError("Invalid date format. Please use YYYY-MM-DD.")
        return value
    
    """
    Validate driver's license expiry date
    """
    def validate_license_expiry_date(self, value):
        if not value:
            raise serializers.ValidationError("License expiry date is required")

        if not self.is_valid_date(value):
            raise serializers.ValidationError("Invalid date format. Please use YYYY-MM-DD.")
        return value

    """
    Validate driver's identification number
    """
    def validate_identification(self, value):
        if not value:
            raise serializers.ValidationError("Identification is required")
        return value

    """
    Create a new driver profile
    """
    def create(self, validated_data):
        pin = validated_data.pop("pin")

        user = User.objects.create(
            phone_number=validated_data["phone_number"],
            role="driver"
        )

        DriverProfile.objects.create(
            user=user,
            pin_hash=make_password(pin),
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

