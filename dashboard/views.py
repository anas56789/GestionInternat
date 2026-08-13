from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.models import Utilisateur
from etudiants.models import Etudiant
from finances.models import Paiement
from hebergement.models import (
    Affectation,
    Batiment,
    Chambre,
    DemandeHebergement,
)
from notifications.models import Notification
from reclamations.models import Reclamation


def verifier_acces_dashboard(utilisateur):
    """
    Autorise uniquement :
    - le superutilisateur ;
    - l'administrateur ;
    - le responsable de l'internat.
    """
    roles_autorises = {
        Utilisateur.Role.ADMINISTRATEUR,
        Utilisateur.Role.RESPONSABLE,
    }

    if (
        not utilisateur.is_authenticated
        or not utilisateur.is_active
        or (
            not utilisateur.is_superuser
            and utilisateur.role not in roles_autorises
        )
    ):
        raise PermissionDenied(
            "Vous n'êtes pas autorisé à accéder à ce tableau de bord."
        )


@login_required
def accueil(request):
    verifier_acces_dashboard(request.user)

    # =========================================================
    # ÉTUDIANTS
    # =========================================================

    nombre_etudiants = Etudiant.objects.count()

    # =========================================================
    # DEMANDES D'HÉBERGEMENT
    # =========================================================

    demandes = DemandeHebergement.objects.all()

    demandes_soumises = demandes.filter(
        statut=DemandeHebergement.Statut.SOUMISE,
    ).count()

    demandes_en_etude = demandes.filter(
        statut=DemandeHebergement.Statut.EN_ETUDE,
    ).count()

    demandes_incompletes = demandes.filter(
        statut=DemandeHebergement.Statut.INCOMPLETE,
    ).count()

    demandes_acceptees = demandes.filter(
        statut=DemandeHebergement.Statut.ACCEPTEE,
    ).count()

    demandes_refusees = demandes.filter(
        statut=DemandeHebergement.Statut.REFUSEE,
    ).count()

    demandes_liste_attente = demandes.filter(
        statut=DemandeHebergement.Statut.LISTE_ATTENTE,
    ).count()

    demandes_en_attente = demandes.filter(
        statut__in={
            DemandeHebergement.Statut.SOUMISE,
            DemandeHebergement.Statut.EN_ETUDE,
            DemandeHebergement.Statut.INCOMPLETE,
        }
    ).count()

    # =========================================================
    # AFFECTATIONS
    # =========================================================

    affectations = Affectation.objects.all()

    affectations_prevues = affectations.filter(
        statut=Affectation.Statut.PREVUE,
    ).count()

    affectations_actives = affectations.filter(
        statut=Affectation.Statut.ACTIVE,
    ).count()

    affectations_cloturees = affectations.filter(
        statut=Affectation.Statut.CLOTUREE,
    ).count()

    affectations_annulees = affectations.filter(
        statut=Affectation.Statut.ANNULEE,
    ).count()

    nombre_affectations_total = affectations.count()

    # =========================================================
    # PAIEMENTS
    # =========================================================

    paiements = Paiement.objects.all()

    paiements_en_attente = paiements.filter(
        statut=Paiement.Statut.EN_ATTENTE,
    ).count()

    paiements_valides = paiements.filter(
        statut=Paiement.Statut.VALIDE,
    ).count()

    paiements_annules = paiements.filter(
        statut=Paiement.Statut.ANNULE,
    ).count()

    paiements_total = paiements.count()

    # =========================================================
    # RÉCLAMATIONS
    # =========================================================

    statuts_reclamations_ouvertes = [
        Reclamation.Statut.NOUVELLE,
        Reclamation.Statut.EN_COURS,
    ]

    # Certaines versions du modèle possèdent EN_ATTENTE.
    if hasattr(
        Reclamation.Statut,
        "EN_ATTENTE",
    ):
        statuts_reclamations_ouvertes.append(
            Reclamation.Statut.EN_ATTENTE,
        )

    reclamations_ouvertes = (
        Reclamation.objects
        .filter(
            statut__in=statuts_reclamations_ouvertes,
        )
        .count()
    )

    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    nombre_notifications_non_lues = (
        Notification.objects
        .filter(
            utilisateur=request.user,
            est_lue=False,
        )
        .count()
    )

    # =========================================================
    # CHAMBRES ET CAPACITÉ
    # =========================================================

    toutes_les_chambres = list(
        Chambre.objects
        .select_related(
            "batiment",
        )
        .prefetch_related(
            "affectations",
        )
        .order_by(
            "batiment__code",
            "etage",
            "numero",
        )
    )

    chambres_actives = [
        chambre
        for chambre in toutes_les_chambres
        if chambre.est_active
    ]

    nombre_chambres = len(
        toutes_les_chambres
    )

    capacite_totale = sum(
        chambre.capacite
        for chambre in chambres_actives
    )

    places_occupees = sum(
        chambre.nombre_places_occupees
        for chambre in chambres_actives
    )

    places_disponibles = max(
        capacite_totale
        - places_occupees,
        0,
    )

    taux_occupation = (
        round(
            (
                places_occupees
                / capacite_totale
            )
            * 100,
            1,
        )
        if capacite_totale > 0
        else 0
    )

    chambres_vides = 0
    chambres_partielles = 0
    chambres_completes = 0
    chambres_indisponibles = 0

    for chambre in toutes_les_chambres:
        if (
            not chambre.est_active
            or chambre.etat
            in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
            }
        ):
            chambres_indisponibles += 1
            continue

        occupation = (
            chambre.nombre_places_occupees
        )

        disponibles = (
            chambre.nombre_places_disponibles
        )

        if occupation <= 0:
            chambres_vides += 1

        elif disponibles <= 0:
            chambres_completes += 1

        else:
            chambres_partielles += 1

    chambres_disponibles = (
        chambres_vides
        + chambres_partielles
    )

    # =========================================================
    # BÂTIMENTS + VISUALISATION DES CHAMBRES
    # =========================================================

    batiments = list(
        Batiment.objects
        .prefetch_related(
            "chambres",
            "chambres__affectations",
        )
        .order_by(
            "code",
        )
    )

    nombre_batiments = len(
        batiments
    )

    batiments_occupation = []

    for batiment in batiments:
        chambres_batiment = list(
            batiment.chambres
            .all()
            .order_by(
                "etage",
                "numero",
            )
        )

        chambres_visualisation = []

        for chambre in chambres_batiment:
            occupation = (
                chambre.nombre_places_occupees
            )

            disponibles = (
                chambre.nombre_places_disponibles
            )

            if (
                not chambre.est_active
                or chambre.etat
                in {
                    Chambre.Etat.MAINTENANCE,
                    Chambre.Etat.HORS_SERVICE,
                }
            ):
                etat_visuel = (
                    "indisponible"
                )

            elif occupation <= 0:
                etat_visuel = "libre"

            elif disponibles <= 0:
                etat_visuel = "complete"

            else:
                etat_visuel = "partielle"

            chambres_visualisation.append(
                {
                    "numero": chambre.numero,
                    "occupation": occupation,
                    "capacite": chambre.capacite,
                    "disponibles": disponibles,
                    "etat": etat_visuel,
                }
            )

        capacite_batiment = (
            batiment.capacite_totale
        )

        occupation_batiment = (
            batiment.nombre_places_occupees
        )

        disponibles_batiment = max(
            capacite_batiment
            - occupation_batiment,
            0,
        )

        taux_batiment = (
            round(
                (
                    occupation_batiment
                    / capacite_batiment
                )
                * 100,
                1,
            )
            if capacite_batiment > 0
            else 0
        )

        batiments_occupation.append(
            {
                "id": batiment.pk,
                "code": batiment.code,
                "nom": batiment.nom,
                "taux": taux_batiment,
                "occupation": occupation_batiment,
                "capacite": capacite_batiment,
                "disponibles": disponibles_batiment,
                "nombre_chambres": len(
                    chambres_batiment
                ),
                "chambres": chambres_visualisation,
            }
        )

    # =========================================================
    # CONTEXTE
    # =========================================================

    contexte = {
        # Utilisateurs
        "nombre_etudiants": nombre_etudiants,

        # Demandes
        "demandes_en_attente": demandes_en_attente,
        "demandes_soumises": demandes_soumises,
        "demandes_en_etude": demandes_en_etude,
        "demandes_incompletes": demandes_incompletes,
        "demandes_acceptees": demandes_acceptees,
        "demandes_refusees": demandes_refusees,
        "demandes_liste_attente": demandes_liste_attente,

        # Affectations
        "nombre_affectations_total": (
            nombre_affectations_total
        ),
        "affectations_prevues": affectations_prevues,
        "affectations_actives": affectations_actives,
        "affectations_cloturees": affectations_cloturees,
        "affectations_annulees": affectations_annulees,

        # Paiements
        "paiements_en_attente": paiements_en_attente,
        "paiements_valides": paiements_valides,
        "paiements_annules": paiements_annules,
        "paiements_total": paiements_total,

        # Réclamations
        "reclamations_ouvertes": reclamations_ouvertes,

        # Notifications
        "nombre_notifications_non_lues": (
            nombre_notifications_non_lues
        ),

        # Chambres / capacité
        "nombre_chambres": nombre_chambres,
        "chambres_disponibles": chambres_disponibles,
        "chambres_vides": chambres_vides,
        "chambres_partielles": chambres_partielles,
        "chambres_completes": chambres_completes,
        "chambres_indisponibles": (
            chambres_indisponibles
        ),
        "capacite_totale": capacite_totale,
        "places_occupees": places_occupees,
        "places_disponibles": places_disponibles,
        "taux_occupation": taux_occupation,

        # Bâtiments
        "nombre_batiments": nombre_batiments,
        "batiments_occupation": batiments_occupation,
    }

    return render(
        request,
        "dashboard/accueil.html",
        contexte,
    )
