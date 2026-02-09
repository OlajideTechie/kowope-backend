from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, permissions
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.models import User
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
            description="Driver registered successfully"
        ),
        400: OpenApiResponse(
            response=None,
            description="Invalid request"
        )
    }
)
class DriverSignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = DriverSignupSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        logger.info(f"New driver registered: {user.phone_number}")

        #generate auth token
        refresh = RefreshToken.for_user(user)

        return Response({
            "success": True,
            'user': UserSerializer(user).data,
            'message': 'User created successfully',
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

        user = serializer.validated_data['user']

        logger.info(f"Driver logged in: {user.email}")

        # Generate auth token
        refresh = RefreshToken.for_user(user)

        return Response({
            "success": True,
            'user': UserSerializer(user).data,
            'message': 'Login successful',
            'token': str(refresh)
        }, status=status.HTTP_200_OK)