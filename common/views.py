from rest_framework import generics, permissions
from drf_spectacular.utils import extend_schema
from .models import Area
from .serializers import AreaSerializer


@extend_schema(tags=["Area"])
class AreaListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AreaSerializer
    queryset = Area.objects.all().order_by("name")
