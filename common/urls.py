from django.urls import path
from .views import AreaListView

app_name = "common"

urlpatterns = [
    path("areas", AreaListView.as_view(), name="area-list"),
]
