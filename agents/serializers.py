# agents/api/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from authentication.models import AgentProfile
from common.models import Area
from services.document_verification_service import DocumentVerificationService

User = get_user_model()


class InviteAgentSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value


class CompleteRegistrationSerializer(serializers.Serializer):
    token = serializers.CharField()
    full_name = serializers.CharField(required=True)
    area = serializers.UUIDField(required=True, help_text="UUID of the area from /api/v1/areas/")
    lga = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    nin_document = serializers.FileField()

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        
        data.pop("confirm_password")  # Remove confirm_password as it's not needed beyond validation

        if len(data["password"]) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in data["password"]):
            raise serializers.ValidationError("Password must contain at least one digit.")
        if not any(char.isalpha() for char in data["password"]):
            raise serializers.ValidationError("Password must contain at least one letter.")
        if not any(char.isupper() for char in data["password"]):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        
        if not any(char in "!@#$%^&*()_+-=[]{}|;':,.<>?/" for char in data["password"]):
            raise serializers.ValidationError("Password must contain at least one special character.")
        if data["password"].lower() in ["password", "12345678", "qwerty"]:
            raise serializers.ValidationError("Password is too common.")
        
        if data["password"].lower() in [data["full_name"].lower(), data["lga"].lower()]:
            raise serializers.ValidationError("Password should not contain personal information.")
        if data["password"].isdigit():
            raise serializers.ValidationError("Password should not be entirely numeric.")
      
        
        if not data["full_name"].strip():
            raise serializers.ValidationError("Full name cannot be empty.")
        if not data.get("area"):
            raise serializers.ValidationError("Area is required.")

        try:
            data["area"] = Area.objects.get(id=data["area"])
        except Area.DoesNotExist:
            raise serializers.ValidationError("Invalid area selected. Choose from /api/v1/areas/")
        if not data["lga"].strip():
            raise serializers.ValidationError("LGA cannot be empty.")
        if not data["password"].strip():
            raise serializers.ValidationError("Password cannot be empty.")
        if not data["nin_document"]:
            raise serializers.ValidationError("NIN document is required.")
        return data

    def validate_token(self, value):
        if not value:
            raise serializers.ValidationError("Token is required.")
        return value

    def validate_nin_document(self, file):
        return DocumentVerificationService.validate_file(file)



class AgentApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])