from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, permissions
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from authentication.models import User, DriverProfile
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.types import OpenApiTypes

from datetime import timedelta
from datetime import datetime

from drf_spectacular import openapi

from authentication.models import DriverDocument, User
from authentication.serializers import (
    DriverSignupSerializer,
    DriverLoginSerializer,
    UserSerializer,
    StaffSignupSerializer,
    StaffLoginSerializer
)

import logging

logger = logging.getLogger(__name__)


@extend_schema(
    request=DriverSignupSerializer,
    responses={
        201: OpenApiResponse(
            response=DriverSignupSerializer,
            description="welcome message with user details"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid request"
        )
    }
)
class DriverSignupView(generics.CreateAPIView):
    serializer_class = DriverSignupSerializer
    permission_classes = [permissions.AllowAny]

    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        data = serializer.validated_data

        """Create user and driver profile within a transaction to ensure atomicity."""
        with transaction.atomic():
            user = User.objects.create(
                phone_number=data["phone_number"],
                role="driver"
            )
            driver_profile = DriverProfile.objects.create(
                user=user,
                full_name=data["full_name"],
                zone=data["zone"],
                lga=data["lga"],
                phone_number=data["phone_number"],
                license_number=data["license_number"],
                is_phone_verified=False,
                verified=False,
                pin_hash=data["pin"]  
            )

            driver_profile.set_pin(data["pin"])

            DriverDocument.objects.create(
                driver=driver_profile,
                document_type=data["document_type"],
                document_file=data["document_file"]
            )

        self.user = user  # Store the created user for use in the response

        logger.info(f"New driver registered as: {user.driver_profile.full_name}")

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        # generate auth token
        refresh = RefreshToken.for_user(self.user)

        return Response({
            "success": True,
            'user': UserSerializer(self.user).data,
            'full_name': self.user.driver_profile.full_name,
            'zone': self.user.driver_profile.zone,
            'lga': self.user.driver_profile.lga,
            'license_number': self.user.driver_profile.license_number,
             'verified': self.user.driver_profile.verified,
            'message': f'Driver Profile created successfully, an otp has been sent for phone verification.',
        }, status=status.HTTP_201_CREATED)



class DriverLoginView(APIView):

    permission_classes = [permissions.AllowAny]
    @extend_schema(
        request=DriverLoginSerializer,
        responses={
            200: OpenApiResponse(
                response=DriverLoginSerializer,
                description="Driver logged in successfully"
            ),
            400: OpenApiResponse(
                response=None,
                description="Invalid credentials"
            )
        }
    )
    def post(self, request):
        serializer = DriverLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data

        try:
            user.driver_profile
        except DriverProfile.DoesNotExist:
            return Response({
                "success": False,
                "message": "User does not have a profile"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # check if phone is verified for first time login
        if not user.driver_profile.is_phone_verified:
            return Response({
                "success": False,
                "message": "Phone number must be verified to log in."
            }, status=status.HTTP_400_BAD_REQUEST)


        # Generate auth token
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        expires_in = datetime.fromtimestamp(access_token.payload['exp']) - datetime.now()

        logger.info(f"Driver logged in as: {user.driver_profile.full_name}")

        return Response({
            "success": True,
            "result": {
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'expires_in': expires_in.total_seconds()
            }
        }, status=status.HTTP_200_OK)