from django.urls import path

from . import views


app_name = "audit"


urlpatterns = [
    path(
        "",
        views.historique_actions,
        name="historique_actions",
    ),
]
