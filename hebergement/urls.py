from django.urls import path

from . import views


app_name = "hebergement"


urlpatterns = [

    # ========================================================
    # ESPACE ÉTUDIANT — DEMANDES
    # ========================================================

    path(
        "demande/deposer/",
        views.deposer_demande,
        name="deposer_demande",
    ),

    path(
        "demande/<int:demande_id>/modifier/",
        views.modifier_demande,
        name="modifier_demande",
    ),

    path(
        "mes-demandes/",
        views.mes_demandes,
        name="mes_demandes",
    ),

    path(
        "demande/<int:demande_id>/",
        views.detail_demande,
        name="detail_demande",
    ),

    path(
    "mon-hebergement/",
    views.mon_hebergement,
    name="mon_hebergement",
    ),


    # ========================================================
    # RESPONSABLE — DEMANDES
    # ========================================================

    path(
        "responsable/demandes/",
        views.liste_demandes_responsable,
        name="liste_demandes_responsable",
    ),

    path(
        "responsable/demandes/<int:demande_id>/",
        views.detail_demande_responsable,
        name="detail_demande_responsable",
    ),

    path(
        "responsable/demandes/<int:demande_id>/traiter/",
        views.traiter_demande,
        name="traiter_demande",
    ),

    path(
        "responsable/demandes-a-affecter/",
        views.liste_demandes_a_affecter,
        name="liste_demandes_a_affecter",
    ),


    # ========================================================
    # RESPONSABLE — CRÉER UNE AFFECTATION
    # ========================================================

    path(
        "responsable/demande/<int:demande_id>/affecter/",
        views.creer_affectation,
        name="creer_affectation",
    ),


    # ========================================================
    # RESPONSABLE — JUSTIFICATIFS
    # ========================================================

    path(
        "responsable/justificatifs/<int:justificatif_id>/valider/",
        views.valider_justificatif,
        name="valider_justificatif",
    ),

    path(
        (
            "responsable/justificatifs/"
            "<int:justificatif_id>/remettre-en-attente/"
        ),
        views.remettre_justificatif_en_attente,
        name="remettre_justificatif_en_attente",
    ),


    # ========================================================
    # RESPONSABLE — AFFECTATIONS
    # ========================================================

    path(
        "responsable/affectations/",
        views.liste_affectations_responsable,
        name="liste_affectations_responsable",
    ),

    path(
        (
            "responsable/affectations/"
            "<int:affectation_id>/confirmer-entree/"
        ),
        views.confirmer_entree_affectation,
        name="confirmer_entree_affectation",
    ),

    path(
        (
            "responsable/affectations/"
            "<int:affectation_id>/cloturer/"
        ),
        views.cloturer_affectation,
        name="cloturer_affectation",
    ),

    path(
        (
            "responsable/affectations/"
            "<int:affectation_id>/transferer/"
        ),
        views.transferer_affectation,
        name="transferer_affectation",
    ),

    path(
        (
            "responsable/affectations/"
            "<int:affectation_id>/annuler/"
        ),
        views.annuler_affectation,
        name="annuler_affectation",
    ),


    # ========================================================
    # RESPONSABLE — TRANSFERTS
    # ========================================================

    path(
        "responsable/transferts/",
        views.liste_transferts_responsable,
        name="liste_transferts_responsable",
    ),


    # ========================================================
    # RESPONSABLE — BÂTIMENTS
    # ========================================================

    path(
        "responsable/batiments/",
        views.liste_batiments,
        name="liste_batiments",
    ),

    path(
        "responsable/batiments/creer/",
        views.creer_batiment,
        name="creer_batiment",
    ),

    path(
        "responsable/batiments/<int:batiment_id>/",
        views.detail_batiment,
        name="detail_batiment",
    ),

    path(
        "responsable/batiments/<int:batiment_id>/modifier/",
        views.modifier_batiment,
        name="modifier_batiment",
    ),


    # ========================================================
    # RESPONSABLE — CHAMBRES
    # ========================================================

    path(
        "responsable/chambres/",
        views.liste_chambres,
        name="liste_chambres",
    ),

    path(
        "responsable/chambres/creer/",
        views.creer_chambre,
        name="creer_chambre",
    ),

    path(
        "responsable/chambres/<int:chambre_id>/modifier/",
        views.modifier_chambre,
        name="modifier_chambre",
    ),

    path(
        "responsable/chambres/<int:chambre_id>/etat/",
        views.changer_etat_chambre,
        name="changer_etat_chambre",
    ),


    # ========================================================
    # RESPONSABLE — ANNÉES UNIVERSITAIRES
    # ========================================================

    path(
        "responsable/annees/",
        views.liste_annees_universitaires,
        name="liste_annees_universitaires",
    ),

    path(
        "responsable/annees/creer/",
        views.creer_annee_universitaire,
        name="creer_annee_universitaire",
    ),

    path(
        "responsable/annees/<int:annee_id>/modifier/",
        views.modifier_annee_universitaire,
        name="modifier_annee_universitaire",
    ),

    path(
        "responsable/annees/<int:annee_id>/activer/",
        views.activer_annee_universitaire,
        name="activer_annee_universitaire",
    ),

    path(
        "responsable/annees/<int:annee_id>/cloturer/",
        views.cloturer_annee_universitaire,
        name="cloturer_annee_universitaire",
    ),
    
]