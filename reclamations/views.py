from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Utilisateur
from audit.models import HistoriqueAction
from notifications.models import creer_notification
from accounts.security import obtenir_profil_etudiant
from .forms import ReclamationForm
from .models import Reclamation


# ============================================================
# ÉTUDIANT — LISTE DE SES RÉCLAMATIONS
# ============================================================


@login_required
def mes_reclamations(request):
    profil = obtenir_profil_etudiant(request)

    reclamations = (
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

    nombre_total = (
        reclamations.count()
    )

    nombre_nouvelles = (
        reclamations
        .filter(
            statut=Reclamation.Statut.NOUVELLE,
        )
        .count()
    )

    nombre_en_cours = (
        reclamations
        .filter(
            statut=Reclamation.Statut.EN_COURS,
        )
        .count()
    )

    nombre_resolues = (
        reclamations
        .filter(
            statut=Reclamation.Statut.RESOLUE,
        )
        .count()
    )

    nombre_rejetees = (
        reclamations
        .filter(
            statut=Reclamation.Statut.REJETEE,
        )
        .count()
    )

    contexte = {
        "reclamations": reclamations,
        "nombre_total": nombre_total,
        "nombre_nouvelles": nombre_nouvelles,
        "nombre_en_cours": nombre_en_cours,
        "nombre_resolues": nombre_resolues,
        "nombre_rejetees": nombre_rejetees,
    }

    return render(
        request,
        "reclamations/etudiant/mes_reclamations.html",
        contexte,
    )



# ============================================================
# ÉTUDIANT — CRÉER UNE RÉCLAMATION
# ============================================================

@login_required
def creer_reclamation(request):
    profil_etudiant = obtenir_profil_etudiant(request)

    if request.method == "POST":
        formulaire = ReclamationForm(
            request.POST,
            request.FILES,
            etudiant=profil_etudiant,
        )

        if formulaire.is_valid():
            reclamation = formulaire.save(
                commit=False
            )

            reclamation.etudiant = profil_etudiant
            reclamation.save()

            messages.success(
                request,
                (
                    "Votre réclamation a été envoyée "
                    "avec succès."
                ),
            )

            return redirect(
                "reclamations:mes_reclamations"
            )

    else:
        formulaire = ReclamationForm(
            etudiant=profil_etudiant,
        )

    return render(
        request,
        "reclamations/etudiant/creer_reclamation.html",
        {
            "formulaire": formulaire,
        },
    )


# ============================================================
# ÉTUDIANT — DÉTAIL D'UNE RÉCLAMATION
# ============================================================

@login_required
def detail_reclamation(
    request,
    reclamation_id,
):
    profil_etudiant = obtenir_profil_etudiant(request)

    reclamation = get_object_or_404(
        Reclamation.objects.select_related(
            "chambre",
            "chambre__batiment",
            "traitee_par",
        ),
        pk=reclamation_id,
        etudiant=profil_etudiant,
    )

    return render(
        request,
        "reclamations/etudiant/detail_reclamation.html",
        {
            "reclamation": reclamation,
        },
    )


# ============================================================
# VÉRIFICATION DU RESPONSABLE
# ============================================================

def verifier_responsable_reclamation(request):
    utilisateur = request.user

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
            (
                "Vous n'êtes pas autorisé à gérer "
                "les réclamations."
            )
        )

    return utilisateur


# ============================================================
# RESPONSABLE — LISTE DES RÉCLAMATIONS
# ============================================================

@login_required
def liste_reclamations_responsable(request):
    verifier_responsable_reclamation(request)

    recherche = request.GET.get("recherche", "").strip()
    statut_selectionne = request.GET.get("statut", "").strip()
    priorite_selectionnee = request.GET.get("priorite", "").strip()
    categorie_selectionnee = request.GET.get("categorie", "").strip()

    toutes_les_reclamations = (
        Reclamation.objects
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "traitee_par",
        )
        .order_by("-date_creation")
    )

    nombre_total_global = toutes_les_reclamations.count()

    nombre_nouvelles = toutes_les_reclamations.filter(
        statut=Reclamation.Statut.NOUVELLE,
    ).count()

    nombre_en_cours = toutes_les_reclamations.filter(
        statut=Reclamation.Statut.EN_COURS,
    ).count()

    nombre_resolues = toutes_les_reclamations.filter(
        statut=Reclamation.Statut.RESOLUE,
    ).count()

    nombre_rejetees = toutes_les_reclamations.filter(
        statut=Reclamation.Statut.REJETEE,
    ).count()

    reclamations = toutes_les_reclamations

    if recherche:
        reclamations = reclamations.filter(
            Q(titre__icontains=recherche)
            | Q(description__icontains=recherche)
            | Q(etudiant__matricule__icontains=recherche)
            | Q(etudiant__cne__icontains=recherche)
            | Q(etudiant__utilisateur__username__icontains=recherche)
            | Q(etudiant__utilisateur__first_name__icontains=recherche)
            | Q(etudiant__utilisateur__last_name__icontains=recherche)
        ).distinct()

    valeurs_statuts = {
        valeur
        for valeur, _libelle
        in Reclamation.Statut.choices
    }

    if (
        statut_selectionne
        and statut_selectionne in valeurs_statuts
    ):
        reclamations = reclamations.filter(
            statut=statut_selectionne,
        )

    valeurs_priorites = {
        valeur
        for valeur, _libelle
        in Reclamation.Priorite.choices
    }

    if (
        priorite_selectionnee
        and priorite_selectionnee in valeurs_priorites
    ):
        reclamations = reclamations.filter(
            priorite=priorite_selectionnee,
        )

    valeurs_categories = {
        valeur
        for valeur, _libelle
        in Reclamation.Categorie.choices
    }

    if (
        categorie_selectionnee
        and categorie_selectionnee in valeurs_categories
    ):
        reclamations = reclamations.filter(
            categorie=categorie_selectionnee,
        )

    contexte = {
        "reclamations": reclamations,
        "recherche": recherche,
        "statut_selectionne": statut_selectionne,
        "priorite_selectionnee": priorite_selectionnee,
        "categorie_selectionnee": categorie_selectionnee,
        "choix_statuts": Reclamation.Statut.choices,
        "choix_priorites": Reclamation.Priorite.choices,
        "choix_categories": Reclamation.Categorie.choices,
        "nombre_reclamations": reclamations.count(),
        "nombre_total_global": nombre_total_global,
        "nombre_nouvelles": nombre_nouvelles,
        "nombre_en_cours": nombre_en_cours,
        "nombre_resolues": nombre_resolues,
        "nombre_rejetees": nombre_rejetees,
    }

    return render(
        request,
        "reclamations/responsable/liste_reclamations.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — DÉTAIL D'UNE RÉCLAMATION
# ============================================================

@login_required
def detail_reclamation_responsable(
    request,
    reclamation_id,
):
    verifier_responsable_reclamation(request)

    reclamation = get_object_or_404(
        Reclamation.objects.select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "traitee_par",
        ),
        pk=reclamation_id,
    )

    return render(
        request,
        "reclamations/responsable/detail_reclamation.html",
        {
            "reclamation": reclamation,
        },
    )


# ============================================================
# RESPONSABLE — TRAITER UNE RÉCLAMATION
# ============================================================

@login_required
@require_POST
@transaction.atomic
def traiter_reclamation(request, reclamation_id):
    utilisateur = verifier_responsable_reclamation(request)

    reclamation = get_object_or_404(
        Reclamation.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "traitee_par",
        ),
        pk=reclamation_id,
    )

    url_detail = (
        "reclamations:detail_reclamation_responsable"
    )

    action = request.POST.get("action", "").strip()
    reponse = request.POST.get("reponse", "").strip()
    motif_rejet = request.POST.get("motif_rejet", "").strip()

    statut_avant = reclamation.statut
    reponse_avant = reclamation.reponse or ""
    motif_rejet_avant = reclamation.motif_rejet or ""

    action_reussie = False
    titre_notification = ""
    message_notification = ""

    statuts_clotures = {
        Reclamation.Statut.RESOLUE,
        Reclamation.Statut.REJETEE,
    }

    if action == "mettre_en_cours":
        if (
            reclamation.statut
            != Reclamation.Statut.NOUVELLE
        ):
            messages.error(
                request,
                (
                    "Seule une réclamation nouvelle "
                    "peut être mise en cours."
                ),
            )
        else:
            reclamation.prendre_en_charge(
                utilisateur
            )

            action_reussie = True
            titre_notification = "Réclamation prise en charge"
            message_notification = (
                f'Votre réclamation « {reclamation.titre} » '
                "est maintenant en cours de traitement."
            )
            messages.success(
                request,
                (
                    "La réclamation est maintenant "
                    "en cours de traitement."
                ),
            )

    elif action == "resoudre":
        if reclamation.statut in statuts_clotures:
            messages.error(
                request,
                "Cette réclamation est déjà clôturée.",
            )
        elif not reponse:
            messages.error(
                request,
                (
                    "La réponse est obligatoire pour "
                    "résoudre la réclamation."
                ),
            )
        else:
            reclamation.motif_rejet = ""
            reclamation.resoudre(
                reponse,
                utilisateur,
            )

            action_reussie = True
            titre_notification = "Réclamation résolue"
            message_notification = (
                f'Votre réclamation « {reclamation.titre} » '
                f"a été résolue. Réponse : {reponse}"
            )
            messages.success(
                request,
                "La réclamation a été résolue avec succès.",
            )

    elif action == "rejeter":
        if reclamation.statut in statuts_clotures:
            messages.error(
                request,
                "Cette réclamation est déjà clôturée.",
            )
        elif not motif_rejet:
            messages.error(
                request,
                "Le motif du rejet est obligatoire.",
            )
        else:
            reclamation.reponse = reponse
            reclamation.rejeter(
                motif_rejet,
                utilisateur,
            )

            action_reussie = True
            titre_notification = "Réclamation rejetée"
            message_notification = (
                f'Votre réclamation « {reclamation.titre} » '
                f"a été rejetée. Motif : {motif_rejet}"
            )
            messages.success(
                request,
                "La réclamation a été rejetée.",
            )

    else:
        messages.error(
            request,
            "Action de traitement invalide.",
        )

    if action_reussie:
        HistoriqueAction.enregistrer_action(
            utilisateur=utilisateur,
            type_action=HistoriqueAction.TypeAction.TRAITEMENT,
            entite="Reclamation",
            identifiant_entite=reclamation.pk,
            description=(
                "Traitement de la réclamation "
                f"« {reclamation.titre} » de l'étudiant "
                f"{reclamation.etudiant.matricule} : "
                f"{reclamation.get_statut_display()}."
            ),
            request=request,
            anciennes_valeurs={
                "statut": statut_avant,
                "reponse": reponse_avant,
                "motif_rejet": motif_rejet_avant,
            },
            nouvelles_valeurs={
                "statut": reclamation.statut,
                "reponse": reclamation.reponse,
                "motif_rejet": reclamation.motif_rejet,
            },
        )

        creer_notification(
            utilisateur=reclamation.etudiant.utilisateur,
            titre=titre_notification,
            message=message_notification,
            type_notification="RECLAMATION",
            lien="/reclamations/mes-reclamations/",
        )

    return redirect(
        url_detail,
        reclamation_id=reclamation.pk,
    )

