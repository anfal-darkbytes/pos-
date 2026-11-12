from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from apps.core.views import manifest_view, service_worker_view, offline_view

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/favicon.svg", permanent=True)),
    path("manifest.json", manifest_view, name="pwa_manifest"),
    path("sw.js", service_worker_view, name="pwa_service_worker"),
    path("offline", offline_view, name="pwa_offline"),
    path("admin/", admin.site.urls),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    path("", include("apps.analytics.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.sales.urls")),
    path("", include("apps.core.urls")),
]

