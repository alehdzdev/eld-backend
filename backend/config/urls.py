# -*- coding: utf-8 -*-
# Django
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, re_path, include
from django.views.i18n import JavaScriptCatalog

# Third Parties
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path(settings.ADMIN_PATH, admin.site.urls),
    re_path(r"^admin/jsi18n/", JavaScriptCatalog.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI:
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # JWT
    path(
        "api/v1/users/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    path("api/v1/users/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path(
        "api/v1/users/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    # YOUR PATTERNS
    path("api/v1/core/", include("core.urls")),
    path("api/v1/users/", include("users.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]
