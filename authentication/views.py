from unittest import result
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
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.throttling import ScopedRateThrottle
from django.core.cache import cache
from django.conf import settings


from datetime import timedelta
from datetime import datetime

from drf_spectacular import openapi

from authentication.models import User
from services.document_verification_service import DocumentVerificationService
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
from authentication.models import AdminProfile, AgentProfile

from services.sms_service import SMSService
from services.otp_service import OTPService
from middleware.permissions import IsDriver, IsAdmin, IsAgent


import logging

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

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"


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
                area=data["area"],
                phone_number=data["phone_number"],
                license_number=data["license_number"],
                is_phone_verified=False,
                verified=False,
                pin_hash=data["pin"]
            )

            driver_profile.set_pin(data["pin"])

            DocumentVerificationService.create_driver_document(
                driver_profile=driver_profile,
                document_type=data["document_type"],
                file=data["document_file"],
            )

        self.user = user  # Store the created user for use in the response

        logger.info(f"New driver registered as: {user.driver_profile.full_name}")

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        # generate auth token
        refresh = RefreshToken.for_user(self.user)

        otp = OTPService.create_otp(
            phone_number=self.user.phone_number, 
            purpose="signup"
        )

        response_data = {
            "success": True,
            'user': UserSerializer(self.user).data,
            'full_name': self.user.driver_profile.full_name,
            'area': self.user.driver_profile.area.name,
            'lga': self.user.driver_profile.area.lga,
            'license_number': self.user.driver_profile.license_number,
            'verified': self.user.driver_profile.verified,
            'message': f'Driver Profile created successfully, your verification otp has been sent',
        }

        if settings.RETURN_OTP_IN_RESPONSE:
            logger.info(f"Signup OTP for {self.user.phone_number}: {otp.code}")
            response_data["otp"] = otp.code
        
        return Response(response_data, status=status.HTTP_201_CREATED)

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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

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
        

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        expires_in = datetime.fromtimestamp(access_token.payload['exp']) - datetime.now()

        logger.info(f"Driver logged in as: {user.driver_profile.full_name}")

        return Response({
            "success": True,
            "result": {
                'user': UserSerializer(user).data,
                'full_name': user.driver_profile.full_name,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
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
    permission_classes = [IsDriver]
    serializer_class = DriverLogoutSerializer

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info(f"Driver logged out as: {request.user.driver_profile.full_name}")

            return Response({
                "success": True,
                "message": "You have been logged out successfully"
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

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    
    def post(self, request):
        serializer_class = VerifyOTPSerializer
        serializer = serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        
        result = OTPService.verify_otp(
                phone_number=phone_number,
                code=code,
                purpose="signup"
            )
        
        if not result["success"]:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "No account found for this phone number. Please register first."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            driver_profile = user.driver_profile

            if driver_profile.is_phone_verified:
                return Response(
                    {"success": False, "message": "User already verified"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark phone as verified and user as verified if not already verified
            driver_profile.is_phone_verified = True
            driver_profile.verified = True
            driver_profile.save(update_fields=["is_phone_verified", "verified"])
                
            logger.info(f"Driver phone verified as: {user.driver_profile.full_name}")

            # Auto login after verification
            refresh_token = RefreshToken.for_user(user)
            access_token = refresh_token.access_token
            
            # calculate token expiry time in seconds eg 300 seconds
            expires_in = datetime.fromtimestamp(access_token.payload['exp']) - datetime.now()

            return Response(
                {
                    "success": True,
                    "result": {
                    "full_name": user.driver_profile.full_name,
                    'user': UserSerializer(user).data,
                    'access_token': str(refresh_token.access_token),
                    'refresh_token': str(refresh_token),
                    'expires_in': expires_in.total_seconds()
            }
                },
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
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

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"


    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # serializer validated driver_profile
        driver_profile = serializer.driver_profile

        #phone_number = normalize_phone(request.data.get("phone_number"))

        # Resend OTP
        otp = OTPService.resend_otp(
                 phone_number=driver_profile.phone_number,
                 purpose="signup"
        )

        response_data = {
            "success": True
        }

        # Only expose OTP in non-production environments
        if settings.RETURN_OTP_IN_RESPONSE:
            response_data["otp"] = otp

        return Response(response_data, status=status.HTTP_200_OK)
    

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

    permission_classes = [IsDriver]
    serializer_class = ChangePinSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
    
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
    


"""API View to handle pin reset request and verification using OTP"""
@extend_schema(
    request=ResetPinSerializer,
    tags=["Driver Authentication"]
)
class ResetPinView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ResetPinSerializer

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reset_pin"


    def post(self, request):
        serializer = ResetPinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        otp_code = serializer.validated_data.get("otp_code")
        new_pin = serializer.validated_data.get("new_pin")

        # Fetch user
        user = (
            User.objects
            .select_related("driver_profile")
            .filter(driver_profile__phone_number=phone_number)
            .first()
        )

        if not user:
            return Response(
                {"success": False, "message": "Phone number not registered."},
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================
        # PHASE 1 — INITIATE RESET
        # =====================================================
        if not otp_code and not new_pin:
            OTPService.create_otp(
                phone_number=phone_number,
                purpose="reset_pin"
            )

            return Response(
                {
                    "success": True,
                    "message": "OTP has been sent to your phone."
                },
                status=status.HTTP_200_OK
            )

        # =====================================================
        # PHASE 2 — VERIFY OTP + RESET PIN
        # =====================================================
        otp_result = OTPService.verify_otp(
            phone_number=phone_number,
            code=otp_code,
            purpose="reset_pin"
        )

        if not otp_result.get("success"):
            return Response(
                {
                    "success": False,
                    "message": otp_result.get("message", "Invalid or expired OTP.")
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            driver_profile = user.driver_profile
            driver_profile.pin_hash = make_password(new_pin)
            driver_profile.save(update_fields=["pin_hash"])

        return Response(
            {
                "success": True,
                "message": "PIN reset successfully. You can now log in."
            },
            status=status.HTTP_200_OK
        )



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
    permission_classes = [IsDriver]
    serializer_class = DriverProfileSerializer

    def get_object(self):
        driver_profile = getattr(self.request.user, "driver_profile", None)
        if not driver_profile:
            return Response(
                {"success": False, "message": "Driver profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        return driver_profile

    def get(self, request, *args, **kwargs):
        user_id = request.user.id
        cache_key = f"driver_profile_{user_id}"
        cached = cache.get(cache_key)

        if cached:
            return Response(cached)

        driver_profile = self.get_object()
        serializer = self.get_serializer(driver_profile, context={"request": request})
        data = serializer.data

        # Cache per-user for 30s so signed URLs stay valid
        cache.set(cache_key, data, timeout=30)
        return Response(data)


@extend_schema(
    request=StaffLoginSerializer,
    tags=["Admin"],
    responses={
        200: OpenApiResponse(description="Admin logged in successfully"),
        401: OpenApiResponse(description="Invalid credentials or insufficient role"),
    },
)
class AdminLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data

        if user.role not in ("admin", "super_admin"):
            return Response(
                {"success": False, "message": "Access denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        expires_in = datetime.fromtimestamp(access_token.payload["exp"]) - datetime.now()

        admin_profile = getattr(user, "admin_profile", None)

        logger.info(f"Admin logged in: {user.email}")

        return Response(
            {
                "success": True,
                "result": {
                    "user": UserSerializer(user).data,
                    "level": admin_profile.level if admin_profile else user.role,
                    "access_token": str(access_token),
                    "refresh_token": str(refresh),
                    "expires_in": expires_in.total_seconds(),
                },
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    request=StaffLoginSerializer,
    tags=["Agent"],
    responses={
        200: OpenApiResponse(description="Agent logged in successfully"),
        403: OpenApiResponse(description="Access denied"),
    },
)
class AgentLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data

        if user.role != "agent":
            return Response(
                {"success": False, "message": "Access denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        agent_profile = getattr(user, "agent_profile", None)
        if not agent_profile:
            return Response(
                {"success": False, "message": "Agent profile not found."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        expires_in = datetime.fromtimestamp(access_token.payload["exp"]) - datetime.now()

        logger.info(f"Agent logged in: {user.email}")

        return Response(
            {
                "success": True,
                "result": {
                    "user": UserSerializer(user).data,
                    "status": agent_profile.status,
                    "access_token": str(access_token),
                    "refresh_token": str(refresh),
                    "expires_in": expires_in.total_seconds(),
                },
            },
            status=status.HTTP_200_OK,
        )
