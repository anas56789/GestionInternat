from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [

    path(
        "admin/",
        admin.site.urls,
    ),

    path(
    "accounts/",
    include("accounts.urls"),
    ),

    path(
        "hebergement/",
        include("hebergement.urls"),
    ),

    path(
        "finances/",
        include("finances.urls"),
    ),

    path(
        "reclamations/",
        include("reclamations.urls"),
    ),

    path(
    "notifications/",
    include("notifications.urls"),
    ),

    path(
    "audit/",
    include("audit.urls"),
    ),

    path(
        "",
        include("dashboard.urls"),
    ),
    path(
    "etudiants/",
    include("etudiants.urls"),
    ),
]



if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )