# agents/api/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class InviteAgentSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    