from django.urls import path

from . import views


app_name = "notifications"


urlpatterns = [
    path(
        "",
        views.mes_notifications,
        name="mes_notifications",
    ),

    path(
        "<int:notification_id>/",
        views.detail_notification,
        name="detail_notification",
    ),

    path(
        "<int:notification_id>/lire/",
        views.marquer_notification_lue,
        name="marquer_notification_lue",
    ),

    path(
        "tout-lire/",
        views.marquer_toutes_lues,
        name="marquer_toutes_lues",
    ),
]
