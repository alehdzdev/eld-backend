# -*- coding: utf-8 -*-
# Django
from django.urls import path, include

# Third Party
from rest_framework.routers import SimpleRouter

router = SimpleRouter()

urlpatterns = [
    path('', include(router.urls)),
]
