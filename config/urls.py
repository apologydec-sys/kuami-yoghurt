from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.accounts.views import AccountLoginView
from apps.core import views as core_views
from apps.core.views import handler404 as _handler404
from apps.core.views import handler500 as _handler500
from apps.dashboard.views import PortalLoginView

handler404 = _handler404
handler500 = _handler500

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls", namespace="core")),
    path("music/", include("apps.music.urls", namespace="music")),
    path("videos/", include("apps.videos.urls", namespace="videos")),
    path("gallery/", include("apps.gallery.urls", namespace="gallery")),
    path("bookings/", include("apps.bookings.urls", namespace="bookings")),
    path("", include("apps.chat.urls", namespace="chat")),
    path(
        "portal/login/",
        PortalLoginView.as_view(),
        name="portal_login",
    ),
    path(
        "portal/logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="portal_logout",
    ),
    path("manifest.webmanifest", core_views.pwa_manifest, name="pwa_manifest"),
    path("service-worker.js", core_views.service_worker, name="service_worker"),
    path("portal/", include("apps.dashboard.urls", namespace="portal")),
    path("dashboard/", include("apps.dashboard.urls", namespace="dashboard")),
    # Authentication
    path("accounts/login/", AccountLoginView.as_view(), name="login"),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="logout",
    ),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
]

# Serve media files during local development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
