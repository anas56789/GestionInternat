from django.urls import path

from . import views


app_name = "reclamations"


urlpatterns = [
    # ========================================================
    # ESPACE ÉTUDIANT
    # ========================================================

    path(
        "mes-reclamations/",
        views.mes_reclamations,
        name="mes_reclamations",
    ),

    path(
        "creer/",
        views.creer_reclamation,
        name="creer_reclamation",
    ),

    path(
        "<int:reclamation_id>/",
        views.detail_reclamation,
        name="detail_reclamation",
    ),

    # ========================================================
    # ESPACE RESPONSABLE
    # ========================================================

    path(
        "responsable/liste/",
        views.liste_reclamations_responsable,
        name="liste_reclamations_responsable",
    ),

    path(
        "responsable/<int:reclamation_id>/",
        views.detail_reclamation_responsable,
        name="detail_reclamation_responsable",
    ),

    path(
        "responsable/<int:reclamation_id>/traiter/",
        views.traiter_reclamation,
        name="traiter_reclamation",
    ),
]
