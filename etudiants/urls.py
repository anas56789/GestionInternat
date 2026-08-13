from django.urls import path

from . import views


app_name = "etudiants"


urlpatterns = [
    path(
        "",
        views.liste_etudiants,
        name="liste_etudiants",
    ),

    path(
        "creer/",
        views.creer_etudiant,
        name="creer_etudiant",
    ),

    path(
    "mon-profil/",
    views.mon_profil,
    name="mon_profil",
    ),

    path(
    "mon-profil/modifier/",
    views.modifier_mon_profil,
    name="modifier_mon_profil",
    ),

    path(
        "<int:etudiant_id>/",
        views.detail_etudiant,
        name="detail_etudiant",
    ),

    path(
        "<int:etudiant_id>/modifier/",
        views.modifier_etudiant,
        name="modifier_etudiant",
    ),

    path(
        "<int:etudiant_id>/statut/",
        views.changer_statut_etudiant,
        name="changer_statut_etudiant",
    ),
]