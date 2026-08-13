from django.core.exceptions import PermissionDenied

from .models import Utilisateur


def verifier_etudiant(request):
    utilisateur = request.user

    if (
        not utilisateur.is_authenticated
        or not utilisateur.is_active
    ):
        raise PermissionDenied(
            "Vous devez être connecté."
        )

    if (
        utilisateur.role
        != Utilisateur.Role.ETUDIANT
        and not utilisateur.is_superuser
    ):
        raise PermissionDenied(
            "Cette page est réservée aux étudiants."
        )

    return utilisateur


def obtenir_profil_etudiant(request):
    utilisateur = verifier_etudiant(request)

    profil = getattr(
        utilisateur,
        "profil_etudiant",
        None,
    )

    if profil is None:
        raise PermissionDenied(
            "Aucun profil étudiant n'est associé à ce compte."
        )

    return profil