# -*- coding: utf-8 -*-
# Django
from django.urls import path

# Third Party
from rest_framework.routers import SimpleRouter

# Local
from core.views import HealthAPIView, generate_trip_plan

router = SimpleRouter()

urlpatterns = [
    # include(router.urls),
    path("health/", HealthAPIView.as_view(), name="health-view"),
    path("generate-plan/", generate_trip_plan, name="generate_trip_plan"),
]
