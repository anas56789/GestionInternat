from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from audit.models import HistoriqueAction

from .forms import (
    InscriptionEtudiantForm,
    UtilisateurCreationForm,
    UtilisateurModificationForm,
)
from .models import Utilisateur
from finances.models import FraisHebergement

from hebergement.models import (
    Affectation,
    DemandeHebergement,
    Justificatif,
)

from notifications.models import Notification

from reclamations.models import Reclamation


# ============================================================
# AUTHENTIFICATION
# ============================================================

def connexion(request):
    if request.user.is_authenticated:
        return rediriger_selon_role(request.user)

    if request.method == "POST":
        username = request.POST.get(
            "username",
            "",
        ).strip()

        password = request.POST.get(
            "password",
            "",
        )

        utilisateur = authenticate(
            request,
            username=username,
            password=password,
        )

        if utilisateur is None:
            messages.error(
                request,
                "Nom d'utilisateur ou mot de passe incorrect.",
            )

        elif not utilisateur.is_active:
            messages.error(
                request,
                "Votre compte est désactivé.",
            )

        else:
            login(request, utilisateur)

            messages.success(
                request,
                (
                    f"Bienvenue "
                    f"{utilisateur.first_name or utilisateur.username}."
                ),
            )

            return rediriger_selon_role(utilisateur)

    return render(
        request,
        "accounts/connexion.html",
    )

@require_http_methods(["GET", "POST"])
def inscription(request):
    if request.user.is_authenticated:
        return rediriger_selon_role(request.user)

    if request.method == "POST":
        formulaire = InscriptionEtudiantForm(
            request.POST
        )

        if formulaire.is_valid():
            utilisateur = formulaire.save()

            messages.success(
                request,
                (
                    "Votre compte étudiant a été créé "
                    "avec succès. Vous pouvez maintenant "
                    "vous connecter."
                ),
            )

            return redirect(
                "accounts:connexion"
            )

    else:
        formulaire = InscriptionEtudiantForm()

    return render(
        request,
        "accounts/inscription.html",
        {
            "formulaire": formulaire,
        },
    )

@login_required
@require_http_methods(["GET", "POST"])
def deconnexion(request):
    # --------------------------------------------------------
    # GET : afficher une confirmation uniquement
    # --------------------------------------------------------

    if request.method == "GET":
        return render(
            request,
            "accounts/deconnexion_confirmation.html",
        )

    # --------------------------------------------------------
    # POST : déconnexion réelle
    # --------------------------------------------------------

    logout(request)

    messages.success(
        request,
        "Vous avez été déconnecté avec succès.",
    )

    return redirect(
        "accounts:connexion"
    )


def rediriger_selon_role(utilisateur):
    if (
        utilisateur.is_superuser
        or utilisateur.role
        in {
            Utilisateur.Role.ADMINISTRATEUR,
            Utilisateur.Role.RESPONSABLE,
        }
    ):
        return redirect("dashboard:accueil")

    if utilisateur.role == Utilisateur.Role.ETUDIANT:
        return redirect("accounts:espace_etudiant")

    return redirect("accounts:connexion")


# ============================================================
# ESPACE ÉTUDIANT
# ============================================================

@login_required
def espace_etudiant(request):
    utilisateur = request.user

    if (
        utilisateur.role != Utilisateur.Role.ETUDIANT
        and not utilisateur.is_superuser
    ):
        raise PermissionDenied(
            "Cette page est réservée aux étudiants."
        )

    profil = getattr(
        utilisateur,
        "profil_etudiant",
        None,
    )

    derniere_demande = None
    affectation_active = None
    frais_hebergement = None
    reclamations_recentes = []
    notifications_recentes = []

    nombre_reclamations_total = 0
    nombre_reclamations_ouvertes = 0
    nombre_reclamations_resolues = 0
    pourcentage_reclamations_resolues = 0

    nombre_notifications_total = 0
    nombre_notifications_lues = 0
    pourcentage_notifications_lues = 0

    nombre_justificatifs = 0
    nombre_justificatifs_en_attente = 0
    nombre_justificatifs_valides = 0
    nombre_justificatifs_rejetes = 0
    pourcentage_justificatifs_valides = 0
    pourcentage_paiement = 0

    if profil is not None:
        derniere_demande = (
            DemandeHebergement.objects
            .filter(
                etudiant=profil,
            )
            .select_related(
                "annee_universitaire",
                "traitee_par",
            )
            .prefetch_related(
                "justificatifs",
            )
            .order_by(
                "-date_creation",
            )
            .first()
        )

        affectation_active = (
            Affectation.objects
            .filter(
                etudiant=profil,
                statut=Affectation.Statut.ACTIVE,
            )
            .select_related(
                "chambre",
                "chambre__batiment",
                "annee_universitaire",
                "demande_hebergement",
            )
            .order_by(
                "-date_creation",
            )
            .first()
        )

        if affectation_active is None:
            affectation_active = (
                Affectation.objects
                .filter(
                    etudiant=profil,
                    statut=Affectation.Statut.PREVUE,
                )
                .select_related(
                    "chambre",
                    "chambre__batiment",
                    "annee_universitaire",
                    "demande_hebergement",
                )
                .order_by(
                    "-date_creation",
                )
                .first()
            )

        frais_hebergement = (
            FraisHebergement.objects
            .filter(
                etudiant=profil,
            )
            .select_related(
                "annee_universitaire",
            )
            .prefetch_related(
                "paiements",
            )
            .order_by(
                "-annee_universitaire__date_debut",
            )
            .first()
        )

        if frais_hebergement is not None:
            montant_total = frais_hebergement.montant_total
            montant_paye = frais_hebergement.montant_paye

            if montant_total and montant_total > 0:
                pourcentage_paiement = round(
                    (montant_paye / montant_total)
                    * 100
                )

                pourcentage_paiement = max(
                    0,
                    min(
                        100,
                        pourcentage_paiement,
                    ),
                )

        reclamations_etudiant = (
            Reclamation.objects
            .filter(
                etudiant=profil,
            )
            .select_related(
                "chambre",
                "chambre__batiment",
            )
            .order_by(
                "-date_creation",
            )
        )

        reclamations_recentes = (
            reclamations_etudiant[:5]
        )

        nombre_reclamations_total = (
            reclamations_etudiant.count()
        )

        nombre_reclamations_ouvertes = (
            reclamations_etudiant
            .filter(
                statut__in=[
                    Reclamation.Statut.NOUVELLE,
                    Reclamation.Statut.EN_COURS,
                ],
            )
            .count()
        )

        nombre_reclamations_resolues = (
            reclamations_etudiant
            .filter(
                statut=Reclamation.Statut.RESOLUE,
            )
            .count()
        )

        if nombre_reclamations_total > 0:
            pourcentage_reclamations_resolues = round(
                (
                    nombre_reclamations_resolues
                    / nombre_reclamations_total
                )
                * 100
            )

        if derniere_demande is not None:
            justificatifs = (
                derniere_demande
                .justificatifs
                .all()
            )

            nombre_justificatifs = (
                justificatifs.count()
            )

            nombre_justificatifs_en_attente = (
                justificatifs
                .filter(
                    statut_validation=(
                        Justificatif
                        .StatutValidation
                        .EN_ATTENTE
                    ),
                )
                .count()
            )

            nombre_justificatifs_valides = (
                justificatifs
                .filter(
                    statut_validation=(
                        Justificatif
                        .StatutValidation
                        .VALIDE
                    ),
                )
                .count()
            )

            nombre_justificatifs_rejetes = (
                justificatifs
                .filter(
                    statut_validation=(
                        Justificatif
                        .StatutValidation
                        .REJETE
                    ),
                )
                .count()
            )

            if nombre_justificatifs > 0:
                pourcentage_justificatifs_valides = round(
                    (
                        nombre_justificatifs_valides
                        / nombre_justificatifs
                    )
                    * 100
                )

    notifications = (
        Notification.objects
        .filter(
            utilisateur=utilisateur,
        )
        .order_by(
            "-date_creation",
        )
    )

    notifications_recentes = (
        notifications[:5]
    )

    nombre_notifications_non_lues = (
        notifications
        .filter(
            est_lue=False,
        )
        .count()
    )

    nombre_notifications_total = (
        notifications.count()
    )

    nombre_notifications_lues = (
        nombre_notifications_total
        - nombre_notifications_non_lues
    )

    if nombre_notifications_total > 0:
        pourcentage_notifications_lues = round(
            (
                nombre_notifications_lues
                / nombre_notifications_total
            )
            * 100
        )

    contexte = {
        "profil": profil,
        "profil_etudiant": profil,

        "derniere_demande": derniere_demande,
        "affectation_active": affectation_active,
        "frais_hebergement": frais_hebergement,

        "pourcentage_paiement": (
            pourcentage_paiement
        ),

        "reclamations_recentes": reclamations_recentes,
        "nombre_reclamations_total": (
            nombre_reclamations_total
        ),
        "nombre_reclamations_ouvertes": (
            nombre_reclamations_ouvertes
        ),
        "nombre_reclamations_resolues": (
            nombre_reclamations_resolues
        ),
        "pourcentage_reclamations_resolues": (
            pourcentage_reclamations_resolues
        ),

        "notifications_recentes": notifications_recentes,
        "nombre_notifications_total": (
            nombre_notifications_total
        ),
        "nombre_notifications_lues": (
            nombre_notifications_lues
        ),
        "nombre_notifications_non_lues": (
            nombre_notifications_non_lues
        ),
        "pourcentage_notifications_lues": (
            pourcentage_notifications_lues
        ),

        "nombre_justificatifs": (
            nombre_justificatifs
        ),
        "nombre_justificatifs_en_attente": (
            nombre_justificatifs_en_attente
        ),
        "nombre_justificatifs_valides": (
            nombre_justificatifs_valides
        ),
        "nombre_justificatifs_rejetes": (
            nombre_justificatifs_rejetes
        ),
        "pourcentage_justificatifs_valides": (
            pourcentage_justificatifs_valides
        ),
    }

    return render(
        request,
        "accounts/espace_etudiant.html",
        contexte,
    )


# ============================================================
# CONTRÔLE D'ACCÈS ADMINISTRATEUR
# ============================================================

def verifier_administrateur(request):
    utilisateur = request.user

    if (
        not utilisateur.is_authenticated
        or not utilisateur.is_active
    ):
        raise PermissionDenied(
            "Vous devez être connecté."
        )

    if (
        not utilisateur.is_superuser
        and utilisateur.role
        != Utilisateur.Role.ADMINISTRATEUR
    ):
        raise PermissionDenied(
            (
                "Seul un administrateur peut "
                "gérer les utilisateurs."
            )
        )

    return utilisateur


# ============================================================
# LISTE DES UTILISATEURS
# ============================================================

@login_required
def liste_utilisateurs(request):
    verifier_administrateur(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    role_selectionne = request.GET.get(
        "role",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    utilisateurs = (
        Utilisateur.objects
        .all()
        .order_by(
            "last_name",
            "first_name",
            "username",
        )
    )

    if recherche:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=recherche)
            | Q(first_name__icontains=recherche)
            | Q(last_name__icontains=recherche)
            | Q(email__icontains=recherche)
        ).distinct()

    roles_valides = {
        valeur
        for valeur, _ in Utilisateur.Role.choices
    }

    if (
        role_selectionne
        and role_selectionne in roles_valides
    ):
        utilisateurs = utilisateurs.filter(
            role=role_selectionne
        )

    if statut_selectionne == "ACTIF":
        utilisateurs = utilisateurs.filter(
            is_active=True
        )

    elif statut_selectionne == "INACTIF":
        utilisateurs = utilisateurs.filter(
            is_active=False
        )

    contexte = {
        "utilisateurs": utilisateurs,
        "recherche": recherche,
        "role_selectionne": role_selectionne,
        "statut_selectionne": statut_selectionne,
        "choix_roles": Utilisateur.Role.choices,
        "nombre_utilisateurs": utilisateurs.count(),
    }

    return render(
        request,
        "accounts/administrateur/liste_utilisateurs.html",
        contexte,
    )


# ============================================================
# CRÉER UN UTILISATEUR
# ============================================================

@login_required
@transaction.atomic
def creer_utilisateur(request):
    administrateur = verifier_administrateur(request)

    if request.method == "POST":
        formulaire = UtilisateurCreationForm(
            request.POST
        )

        if formulaire.is_valid():
            utilisateur = formulaire.save(
                commit=False
            )

            utilisateur.is_staff = (
                utilisateur.role
                in {
                    Utilisateur.Role.ADMINISTRATEUR,
                    Utilisateur.Role.RESPONSABLE,
                }
            )

            utilisateur.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=administrateur,
                type_action=(
                    HistoriqueAction.TypeAction.CREATION
                ),
                entite="Utilisateur",
                identifiant_entite=utilisateur.pk,
                description=(
                    "Création du compte utilisateur "
                    f"{utilisateur.username}."
                ),
                request=request,
                nouvelles_valeurs={
                    "username": utilisateur.username,
                    "first_name": utilisateur.first_name,
                    "last_name": utilisateur.last_name,
                    "email": utilisateur.email,
                    "role": utilisateur.role,
                    "is_active": utilisateur.is_active,
                    "is_staff": utilisateur.is_staff,
                },
            )

            messages.success(
                request,
                (
                    f"Le compte de "
                    f"{utilisateur.username} "
                    "a été créé avec succès."
                ),
            )

            return redirect(
                "accounts:liste_utilisateurs"
            )

    else:
        formulaire = UtilisateurCreationForm()

    return render(
        request,
        "accounts/administrateur/formulaire_utilisateur.html",
        {
            "formulaire": formulaire,
            "titre_page": "Créer un utilisateur",
            "bouton_validation": "Créer le compte",
        },
    )


# ============================================================
# DÉTAIL D'UN UTILISATEUR
# ============================================================

@login_required
def detail_utilisateur(
    request,
    utilisateur_id,
):
    verifier_administrateur(request)

    utilisateur = get_object_or_404(
        Utilisateur,
        pk=utilisateur_id,
    )

    profil_etudiant = getattr(
        utilisateur,
        "profil_etudiant",
        None,
    )

    return render(
        request,
        "accounts/administrateur/detail_utilisateur.html",
        {
            "utilisateur_consulte": utilisateur,
            "profil_etudiant": profil_etudiant,
        },
    )


# ============================================================
# MODIFIER UN UTILISATEUR
# ============================================================

@login_required
@transaction.atomic
def modifier_utilisateur(
    request,
    utilisateur_id,
):
    administrateur = verifier_administrateur(request)

    utilisateur = get_object_or_404(
        Utilisateur.objects.select_for_update(),
        pk=utilisateur_id,
    )

    valeurs_avant_modification = {
        "username": utilisateur.username,
        "first_name": utilisateur.first_name,
        "last_name": utilisateur.last_name,
        "email": utilisateur.email,
        "role": utilisateur.role,
        "is_active": utilisateur.is_active,
        "is_staff": utilisateur.is_staff,
    }

    if request.method == "POST":
        formulaire = UtilisateurModificationForm(
            request.POST,
            instance=utilisateur,
        )

        if formulaire.is_valid():
            utilisateur = formulaire.save(
                commit=False
            )

            utilisateur.is_staff = (
                utilisateur.is_superuser
                or utilisateur.role
                in {
                    Utilisateur.Role.ADMINISTRATEUR,
                    Utilisateur.Role.RESPONSABLE,
                }
            )

            utilisateur.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=administrateur,
                type_action=(
                    HistoriqueAction.TypeAction.MODIFICATION
                ),
                entite="Utilisateur",
                identifiant_entite=utilisateur.pk,
                description=(
                    "Modification du compte utilisateur "
                    f"{utilisateur.username}."
                ),
                request=request,
                anciennes_valeurs=(
                    valeurs_avant_modification
                ),
                nouvelles_valeurs={
                    "username": utilisateur.username,
                    "first_name": utilisateur.first_name,
                    "last_name": utilisateur.last_name,
                    "email": utilisateur.email,
                    "role": utilisateur.role,
                    "is_active": utilisateur.is_active,
                    "is_staff": utilisateur.is_staff,
                },
            )

            messages.success(
                request,
                (
                    f"Le compte de "
                    f"{utilisateur.username} "
                    "a été modifié avec succès."
                ),
            )

            return redirect(
                "accounts:detail_utilisateur",
                utilisateur_id=utilisateur.pk,
            )

    else:
        formulaire = UtilisateurModificationForm(
            instance=utilisateur
        )

    return render(
        request,
        "accounts/administrateur/formulaire_utilisateur.html",
        {
            "formulaire": formulaire,
            "utilisateur_consulte": utilisateur,
            "titre_page": "Modifier un utilisateur",
            "bouton_validation": "Enregistrer",
        },
    )


# ============================================================
# ACTIVER OU DÉSACTIVER UN UTILISATEUR
# ============================================================

@login_required
@transaction.atomic
def changer_statut_utilisateur(
    request,
    utilisateur_id,
):
    administrateur = verifier_administrateur(request)

    utilisateur = get_object_or_404(
        Utilisateur.objects.select_for_update(),
        pk=utilisateur_id,
    )

    if request.method != "POST":
        return redirect(
            "accounts:detail_utilisateur",
            utilisateur_id=utilisateur.pk,
        )

    if utilisateur.pk == request.user.pk:
        messages.error(
            request,
            (
                "Vous ne pouvez pas désactiver "
                "votre propre compte."
            ),
        )

        return redirect(
            "accounts:detail_utilisateur",
            utilisateur_id=utilisateur.pk,
        )

    if utilisateur.is_superuser:
        messages.error(
            request,
            (
                "Le statut d'un superutilisateur "
                "ne peut pas être modifié ici."
            ),
        )

        return redirect(
            "accounts:detail_utilisateur",
            utilisateur_id=utilisateur.pk,
        )

    statut_avant_modification = utilisateur.is_active

    utilisateur.is_active = not utilisateur.is_active

    utilisateur.save(
        update_fields=[
            "is_active",
        ]
    )

    HistoriqueAction.enregistrer_action(
        utilisateur=administrateur,
        type_action=(
            HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="Utilisateur",
        identifiant_entite=utilisateur.pk,
        description=(
            f"{'Activation' if utilisateur.is_active else 'Désactivation'} "
            f"du compte {utilisateur.username}."
        ),
        request=request,
        anciennes_valeurs={
            "is_active": statut_avant_modification,
        },
        nouvelles_valeurs={
            "is_active": utilisateur.is_active,
        },
    )

    if utilisateur.is_active:
        messages.success(
            request,
            (
                f"Le compte de {utilisateur.username} "
                "a été activé."
            ),
        )

    else:
        messages.success(
            request,
            (
                f"Le compte de {utilisateur.username} "
                "a été désactivé."
            ),
        )

    return redirect(
        "accounts:detail_utilisateur",
        utilisateur_id=utilisateur.pk,
    )