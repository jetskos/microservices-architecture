from django.contrib import admin
from django.urls import path

from .views import health, me, metrics

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health, name="health"),
    path("metrics", metrics, name="metrics"),
    path("api/me", me, name="me"),
]
