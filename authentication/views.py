from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, permissions
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from urllib3 import Retry
from authentication.models import OTP, User, DriverProfile
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.types import OpenApiTypes


from datetime import timedelta
from datetime import datetime

from drf_spectacular import openapi

from authentication.models import DriverDocument, User
from authentication.serializers import (
    DriverSignupSerializer,
    DriverLoginSerializer,
    UserSerializer,
    DriverLogoutSerializer,
    StaffSignupSerializer,
    StaffLoginSerializer,
    VerifyOTPSerializer,
    DriverProfileSerializer,
    ResetPinSerializer,
    ChangePinSerializer,
    ResendOTPSerializer,
)

import logging

from authentication.services.sms_service import SMSService
from authentication.services.otp_service import OTPService

logger = logging.getLogger(__name__)


@extend_schema(
    request=DriverSignupSerializer,
    tags=["Driver Authentication"],
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

        OTPService.create_otp(phone_number=self.user.phone_number, purpose="signup")

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


@extend_schema(
    request=DriverLoginSerializer,
    tags=["Driver Authentication"],
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
    

@extend_schema(
    request=DriverLogoutSerializer,
    tags=["Driver Authentication"],
    responses={
        200: OpenApiResponse(
            response=None,
            description="Driver logged out successfully"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid request"
        )
    }
)
class DriverLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DriverLogoutSerializer

    @extend_schema(
        request=None,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Driver logged out successfully"
            ),
            400: OpenApiResponse(
                response=None,
                description="Invalid request"
            )
        }
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info(f"Driver logged out as: {request.user.driver_profile.full_name}")

            return Response({
                "success": True,
                "message": "Logged out successfully"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "success": False,
                "message": "Invalid refresh token"
            }, status=status.HTTP_400_BAD_REQUEST)
        

"""API View to verify OTP for phone number verification and other purposes"""

@extend_schema(
    request=VerifyOTPSerializer,
    tags=["Driver Authentication"],
    responses={
        200: OpenApiResponse(
            response=None,
            description="OTP verified successfully"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid OTP or phone number"
        )
    }
)
class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
            phone_number = request.data.get("phone_number")
            otp = request.data.get("otp")

            if not phone_number or not otp:
                return Response(
                    {"success": False, "message": "Phone number and OTP are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            result = OTPService.verify_otp(
                phone_number=phone_number,
                otp=otp,
                purpose="signup"
            )

            if not result["success"]:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.filter(phone_number=phone_number, role="driver").first()
            driver = DriverProfile.objects.filter(user=user).first()

            user.is_active = True
            user.save(update_fields=["is_active"])

            driver.is_phone_verified = True
            driver.save(update_fields=["is_phone_verified"])

            return Response(
                {
                    "success": True,
                    "message": "Phone number verified. You can now log in."
                },
                status=status.HTTP_200_OK
            )


@extend_schema(
    request=ResendOTPSerializer,
    tags=["Driver Authentication"],
    responses={
        200: OpenApiResponse(
            response=None,
            description="A new OTP has been sent"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid phone number"
        )
    }
)
class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ResendOTPSerializer

    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response(
                {"success": False, "message": "Phone number is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = OTPService.resend_otp(
            phone_number=phone_number,
            purpose="phone_verification"
        )

        return Response(result, status=status.HTTP_200_OK)
    

@extend_schema(
    request=ChangePinSerializer,
    tags=["Driver Authentication"],
    responses={
        200: OpenApiResponse(
            response=None,
            description="PIN changed successfully"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid old PIN or new PIN"
        )
    }
)
class ChangePinView(APIView):

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePinSerializer

    def post(self, request):
        user = request.user
        driver_profile = user.driver_profile

        old_pin = request.data.get("old_pin")
        new_pin = request.data.get("new_pin")

        if not driver_profile.check_pin(old_pin):
            return Response({"error": "Old PIN is incorrect"}, status=400)

        driver_profile.set_pin(new_pin)

        return Response({
            "success": True,
            "message": "PIN changed successfully"
        })
    


"""API View to retrieve the authenticated driver's profile information"""

@extend_schema(
    request=None,
    tags=["Driver Profile"],
    responses={
        200: OpenApiResponse(
            response=DriverProfileSerializer,
            description="Driver profile retrieved successfully"
        ),
        404: OpenApiResponse(
            response=None,
            description="Driver profile not found"
        )
    }
)
class DriverProfileView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DriverProfileSerializer

    def get_object(self):
        driver_profile = self.request.user.driver_profile
        if not driver_profile:
            return Response({
                "success": False,
                "message": "Driver profile not found"
            }, status=status.HTTP_404_NOT_FOUND)
        return driver_profile