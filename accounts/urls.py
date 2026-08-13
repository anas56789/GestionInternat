from django.urls import path

from . import views


app_name = "accounts"


urlpatterns = [

    # ========================================================
    # AUTHENTIFICATION
    # ========================================================

    path(
        "connexion/",
        views.connexion,
        name="connexion",
    ),

    path(
        "inscription/",
        views.inscription,
        name="inscription",
    ),

    path(
        "deconnexion/",
        views.deconnexion,
        name="deconnexion",
    ),


    # ========================================================
    # ESPACE ÉTUDIANT
    # ========================================================

    path(
        "espace-etudiant/",
        views.espace_etudiant,
        name="espace_etudiant",
    ),


    # ========================================================
    # ADMINISTRATION DES UTILISATEURS
    # ========================================================

    path(
        "utilisateurs/",
        views.liste_utilisateurs,
        name="liste_utilisateurs",
    ),

    path(
        "utilisateurs/creer/",
        views.creer_utilisateur,
        name="creer_utilisateur",
    ),

    path(
        "utilisateurs/<int:utilisateur_id>/",
        views.detail_utilisateur,
        name="detail_utilisateur",
    ),

    path(
        "utilisateurs/<int:utilisateur_id>/modifier/",
        views.modifier_utilisateur,
        name="modifier_utilisateur",
    ),

    path(
        "utilisateurs/<int:utilisateur_id>/statut/",
        views.changer_statut_utilisateur,
        name="changer_statut_utilisateur",
    ),
]