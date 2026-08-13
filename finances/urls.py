from django.urls import path

from . import views


app_name = "finances"


urlpatterns = [
    # ========================================================
    # RESPONSABLE / ADMINISTRATION
    # ========================================================

    path(
        "",
        views.liste_frais,
        name="liste_frais",
    ),
    path(
        "creer/",
        views.creer_frais,
        name="creer_frais",
    ),
    path(
        "frais/<int:frais_id>/",
        views.detail_frais,
        name="detail_frais",
    ),
    path(
        "frais/<int:frais_id>/modifier/",
        views.modifier_frais,
        name="modifier_frais",
    ),
    path(
        "frais/<int:frais_id>/paiement/",
        views.enregistrer_paiement,
        name="enregistrer_paiement",
    ),
    path(
        "paiement/<int:paiement_id>/valider/",
        views.valider_paiement,
        name="valider_paiement",
    ),
    path(
        "paiement/<int:paiement_id>/annuler/",
        views.annuler_paiement,
        name="annuler_paiement",
    ),
    path(
        "paiements/en-attente/",
        views.liste_paiements_en_attente,
        name="liste_paiements_en_attente",
    ),
    path(
        "paiement/<int:paiement_id>/recu/",
        views.recu_paiement_responsable,
        name="recu_paiement_responsable",
    ),

    # ========================================================
    # ESPACE ÉTUDIANT
    # ========================================================

    path(
        "ma-situation/",
        views.ma_situation_financiere,
        name="ma_situation_financiere",
    ),
    path(
        "mes-frais/<int:frais_id>/",
        views.detail_frais_etudiant,
        name="detail_frais_etudiant",
    ),
    path(
        "mes-frais/<int:frais_id>/declarer-paiement/",
        views.declarer_paiement_etudiant,
        name="declarer_paiement_etudiant",
    ),
    path(
        "mes-paiements/<int:paiement_id>/recu/",
        views.recu_paiement_etudiant,
        name="recu_paiement_etudiant",
    ),
]
