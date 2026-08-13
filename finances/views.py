from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Utilisateur
from accounts.security import obtenir_profil_etudiant
from audit.models import HistoriqueAction
from notifications.models import creer_notification

from decimal import Decimal
from .forms import (
     AnnulationPaiementForm,
     DeclarationPaiementEtudiantForm,
     FraisHebergementForm,
     PaiementForm,
)
from .models import FraisHebergement, Paiement


# ============================================================
# CONTRÔLE D'ACCÈS — RESPONSABLE ET ADMINISTRATEUR
# ============================================================

def verifier_responsable_finances(request):
    """
    Autorise :
    - le superutilisateur ;
    - l'administrateur ;
    - le responsable de l'internat.
    """
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
            "Vous n'êtes pas autorisé à gérer les finances."
        )

    return utilisateur


# ============================================================
# OUTIL — CODE DU STATUT FINANCIER
# ============================================================

def obtenir_code_statut_financier(frais):
    """
    Convertit le texte retourné par statut_financier
    en code utilisable dans les filtres.
    """
    statut = frais.statut_financier.lower().strip()

    if "retard" in statut:
        return "RETARD"

    if statut == "payé":
        return "PAYE"

    if statut.startswith("partiellement"):
        return "PARTIEL"

    return "NON_PAYE"


# ============================================================
# RESPONSABLE — LISTE DES FRAIS
# ============================================================


@login_required
def liste_frais(request):
    verifier_responsable_finances(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    annee_selectionnee = request.GET.get(
        "annee",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    frais = (
        FraisHebergement.objects
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
            "cree_par",
        )
        .prefetch_related("paiements")
        .order_by(
            "-annee_universitaire__date_debut",
            "etudiant__matricule",
        )
    )

    if recherche:
        frais = frais.filter(
            Q(
                etudiant__matricule__icontains=recherche
            )
            | Q(
                etudiant__cne__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__username__icontains=(
                    recherche
                )
            )
            | Q(
                etudiant__utilisateur__first_name__icontains=(
                    recherche
                )
            )
            | Q(
                etudiant__utilisateur__last_name__icontains=(
                    recherche
                )
            )
        ).distinct()

    if annee_selectionnee:
        frais = frais.filter(
            annee_universitaire_id=annee_selectionnee,
        )

    liste_frais = list(frais)

    statuts_valides = {
        "NON_PAYE",
        "PARTIEL",
        "PAYE",
        "RETARD",
    }

    if (
        statut_selectionne
        and statut_selectionne in statuts_valides
    ):
        liste_frais = [
            objet
            for objet in liste_frais
            if obtenir_code_statut_financier(objet)
            == statut_selectionne
        ]

    annees = (
        FraisHebergement.objects
        .values(
            "annee_universitaire_id",
            "annee_universitaire__libelle",
        )
        .distinct()
        .order_by(
            "-annee_universitaire__libelle",
        )
    )

    montant_total = sum(
        objet.montant_total
        for objet in liste_frais
    )

    montant_paye = sum(
        objet.montant_paye
        for objet in liste_frais
    )

    montant_restant = sum(
        objet.montant_restant
        for objet in liste_frais
    )

    nombre_dossiers_soldes = sum(
        1
        for objet in liste_frais
        if objet.est_solde
    )

    nombre_dossiers_en_retard = sum(
        1
        for objet in liste_frais
        if obtenir_code_statut_financier(objet)
        == "RETARD"
    )

    contexte = {
        "frais": liste_frais,

        "recherche": recherche,
        "annee_selectionnee": annee_selectionnee,
        "statut_selectionne": statut_selectionne,
        "annees": annees,

        "nombre_frais": len(liste_frais),
        "montant_total": montant_total,
        "montant_paye": montant_paye,
        "montant_restant": montant_restant,
        "nombre_dossiers_soldes": (
            nombre_dossiers_soldes
        ),
        "nombre_dossiers_en_retard": (
            nombre_dossiers_en_retard
        ),
    }

    return render(
        request,
        (
            "finances/responsable/"
            "situations_financieres.html"
        ),
        contexte,
    )



# ============================================================
# RESPONSABLE — CRÉER DES FRAIS
# ============================================================

@login_required
@transaction.atomic
def creer_frais(request):
    utilisateur = verifier_responsable_finances(request)

    if request.method == "POST":
        formulaire = FraisHebergementForm(
            request.POST
        )

        if formulaire.is_valid():
            frais = formulaire.save(commit=False)
            frais.cree_par = utilisateur

            try:
                frais.full_clean()
                frais.save()

            except IntegrityError:
                formulaire.add_error(
                    None,
                    (
                        "Des frais existent déjà pour cet "
                        "étudiant et cette année universitaire."
                    ),
                )

            except ValidationError as erreur:
                if hasattr(erreur, "message_dict"):
                    for champ, erreurs in erreur.message_dict.items():
                        for message in erreurs:
                            formulaire.add_error(
                                champ
                                if champ in formulaire.fields
                                else None,
                                message,
                            )
                else:
                    formulaire.add_error(
                        None,
                        " ".join(erreur.messages),
                    )

            else:
                HistoriqueAction.enregistrer_action(
                    utilisateur=utilisateur,
                    type_action=(
                        HistoriqueAction.TypeAction.CREATION
                    ),
                    entite="FraisHebergement",
                    identifiant_entite=frais.pk,
                    description=(
                        "Création des frais d'hébergement "
                        f"de l'étudiant "
                        f"{frais.etudiant.matricule} "
                        f"pour l'année "
                        f"{frais.annee_universitaire.libelle}."
                    ),
                    request=request,
                    nouvelles_valeurs={
                        "etudiant": frais.etudiant.matricule,
                        "annee_universitaire": (
                            frais.annee_universitaire.libelle
                        ),
                        "montant_total": str(
                            frais.montant_total
                        ),
                        "date_echeance": str(
                            frais.date_echeance
                        ),
                        "est_actif": frais.est_actif,
                    },
                )

                creer_notification(
                    utilisateur=frais.etudiant.utilisateur,
                    titre="Nouveaux frais d'hébergement",
                    message=(
                        "Des frais d'hébergement d'un montant "
                        f"total de {frais.montant_total} DH "
                        "ont été enregistrés pour l'année "
                        f"{frais.annee_universitaire.libelle}."
                    ),
                    type_notification="PAIEMENT",
                    lien="/finances/ma-situation/",
                )

                messages.success(
                    request,
                    (
                        "Les frais d'hébergement ont été "
                        "créés avec succès."
                    ),
                )

                return redirect(
                    "finances:detail_frais",
                    frais_id=frais.pk,
                )

    else:
        formulaire = FraisHebergementForm()

    return render(
        request,
        "finances/responsable/creer_frais.html",
        {
            "formulaire": formulaire,
        },
    )


# ============================================================
# RESPONSABLE — DÉTAIL DES FRAIS
# ============================================================

@login_required
def detail_frais(request, frais_id):
    verifier_responsable_finances(request)

    frais = get_object_or_404(
        FraisHebergement.objects.select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
            "cree_par",
        ),
        pk=frais_id,
    )

    paiements = (
        frais.paiements
        .select_related("enregistre_par")
        .order_by(
            "-date_paiement",
            "-date_creation",
        )
    )

    formulaire_paiement = PaiementForm(
        frais_hebergement=frais,
    )

    return render(
    request,
    "finances/responsable/detail_situation.html",
    {
        "frais": frais,
        "paiements": paiements,
        "formulaire_paiement": formulaire_paiement,
    },
)


# ============================================================
# RESPONSABLE — MODIFIER DES FRAIS
# ============================================================

@login_required
@transaction.atomic
def modifier_frais(request, frais_id):
    utilisateur = verifier_responsable_finances(request)

    frais = get_object_or_404(
        FraisHebergement.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "annee_universitaire",
        ),
        pk=frais_id,
    )

    valeurs_avant_modification = {
        "montant_total": str(frais.montant_total),
        "date_echeance": str(frais.date_echeance),
        "est_actif": frais.est_actif,
        "commentaire": frais.commentaire,
    }

    if request.method == "POST":
        formulaire = FraisHebergementForm(
            request.POST,
            instance=frais,
        )

        if formulaire.is_valid():
            frais_modifies = formulaire.save(
                commit=False
            )

            try:
                frais_modifies.full_clean()
                frais_modifies.save()

            except IntegrityError:
                formulaire.add_error(
                    None,
                    (
                        "Des frais existent déjà pour cet "
                        "étudiant et cette année universitaire."
                    ),
                )

            except ValidationError as erreur:
                if hasattr(erreur, "message_dict"):
                    for champ, erreurs in erreur.message_dict.items():
                        for message in erreurs:
                            formulaire.add_error(
                                champ
                                if champ in formulaire.fields
                                else None,
                                message,
                            )
                else:
                    formulaire.add_error(
                        None,
                        " ".join(erreur.messages),
                    )

            else:
                HistoriqueAction.enregistrer_action(
                    utilisateur=utilisateur,
                    type_action=(
                        HistoriqueAction.TypeAction.MODIFICATION
                    ),
                    entite="FraisHebergement",
                    identifiant_entite=frais_modifies.pk,
                    description=(
                        "Modification des frais "
                        f"d'hébergement de l'étudiant "
                        f"{frais_modifies.etudiant.matricule}."
                    ),
                    request=request,
                    anciennes_valeurs=(
                        valeurs_avant_modification
                    ),
                    nouvelles_valeurs={
                        "montant_total": str(
                            frais_modifies.montant_total
                        ),
                        "date_echeance": str(
                            frais_modifies.date_echeance
                        ),
                        "est_actif": (
                            frais_modifies.est_actif
                        ),
                        "commentaire": (
                            frais_modifies.commentaire
                        ),
                    },
                )

            creer_notification(
    utilisateur=(
        frais_modifies.etudiant.utilisateur
    ),
    titre="Modification de vos frais d'hébergement",
    message=(
        "Votre situation financière pour l'année "
        f"{frais_modifies.annee_universitaire.libelle} "
        "a été mise à jour. "
        f"Nouveau montant total : "
        f"{frais_modifies.montant_total} DH. "
        f"Nouvelle échéance : "
        f"{frais_modifies.date_echeance:%d/%m/%Y}. "
        f"Montant restant : "
        f"{frais_modifies.montant_restant} DH."
    ),
    type_notification="PAIEMENT",
    lien="/finances/ma-situation/",
)

            messages.success(
                    request,
                    (
                        "Les frais d'hébergement ont été "
                        "modifiés avec succès."
                    ),
                )

            return redirect(
                    "finances:detail_frais",
                    frais_id=frais_modifies.pk,
                )

    else:
        formulaire = FraisHebergementForm(
            instance=frais
        )



    return render(
        request,
        "finances/responsable/modifier_frais.html",
        {
            "formulaire": formulaire,
            "frais": frais,
        },
    )


# ============================================================
# RESPONSABLE — ENREGISTRER UN PAIEMENT
# ============================================================

@login_required
@require_POST
@transaction.atomic
def enregistrer_paiement(request, frais_id):
    utilisateur = verifier_responsable_finances(request)

    frais = get_object_or_404(
        FraisHebergement.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
        ),
        pk=frais_id,
        est_actif=True,
    )

    formulaire = PaiementForm(
        request.POST,
        frais_hebergement=frais,
    )

    if formulaire.is_valid():
        paiement = formulaire.save(commit=False)

        paiement.frais_hebergement = frais
        paiement.enregistre_par = utilisateur
        paiement.statut = Paiement.Statut.EN_ATTENTE

        try:
            paiement.full_clean()
            paiement.save()

        except ValidationError as erreur:
            if hasattr(erreur, "message_dict"):
                for champ, erreurs in erreur.message_dict.items():
                    for message in erreurs:
                        formulaire.add_error(
                            champ
                            if champ in formulaire.fields
                            else None,
                            message,
                        )
            else:
                formulaire.add_error(
                    None,
                    " ".join(erreur.messages),
                )

        else:
            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur,
                type_action=(
                    HistoriqueAction.TypeAction.CREATION
                ),
                entite="Paiement",
                identifiant_entite=paiement.pk,
                description=(
                    "Enregistrement d'un paiement de "
                    f"{paiement.montant} DH pour "
                    f"l'étudiant "
                    f"{frais.etudiant.matricule}."
                ),
                request=request,
                nouvelles_valeurs={
                    "montant": str(paiement.montant),
                    "mode_paiement": paiement.mode_paiement,
                    "date_paiement": str(
                        paiement.date_paiement
                    ),
                    "reference": paiement.reference,
                    "statut": paiement.statut,
                },
            )

            messages.success(
                request,
                (
                    "Le paiement a été enregistré. "
                    "Il est en attente de validation."
                ),
            )

            return redirect(
                "finances:detail_frais",
                frais_id=frais.pk,
            )

    paiements = (
        frais.paiements
        .select_related("enregistre_par")
        .order_by(
            "-date_paiement",
            "-date_creation",
        )
    )

    return render(
        request,
        "finances/responsable/detail_situation.html",
        {
            "frais": frais,
            "paiements": paiements,
            "formulaire_paiement": formulaire,
        },
    )


# ============================================================
# RESPONSABLE — VALIDER UN PAIEMENT
# ============================================================

@login_required
@require_POST
@transaction.atomic
def valider_paiement(request, paiement_id):
    utilisateur = verifier_responsable_finances(request)

    paiement = get_object_or_404(
        Paiement.objects
        .select_for_update()
        .select_related(
            "frais_hebergement",
            "frais_hebergement__etudiant",
            "frais_hebergement__etudiant__utilisateur",
            "frais_hebergement__annee_universitaire",
        ),
        pk=paiement_id,
    )

    frais = paiement.frais_hebergement

    if paiement.statut != Paiement.Statut.EN_ATTENTE:
        messages.error(
            request,
            (
                "Seul un paiement en attente peut "
                "être validé."
            ),
        )

        return redirect(
            "finances:detail_frais",
            frais_id=frais.pk,
        )

    statut_avant_validation = paiement.statut

    try:
        paiement.valider()

    except ValidationError as erreur:
        messages.error(
            request,
            " ".join(erreur.messages),
        )

    else:
        frais.refresh_from_db()

        HistoriqueAction.enregistrer_action(
            utilisateur=utilisateur,
            type_action=(
                HistoriqueAction.TypeAction.VALIDATION
            ),
            entite="Paiement",
            identifiant_entite=paiement.pk,
            description=(
                "Validation du paiement de "
                f"{paiement.montant} DH pour "
                f"l'étudiant "
                f"{frais.etudiant.matricule}."
            ),
            request=request,
            anciennes_valeurs={
                "statut": statut_avant_validation,
            },
            nouvelles_valeurs={
                "statut": paiement.statut,
                "montant": str(paiement.montant),
            },
        )

        creer_notification(
            utilisateur=frais.etudiant.utilisateur,
            titre="Paiement validé",
            message=(
                f"Votre paiement de "
                f"{paiement.montant} DH a été validé. "
                f"Le montant restant est de "
                f"{frais.montant_restant} DH."
            ),
            type_notification="PAIEMENT",
            lien="/finances/ma-situation/",
        )

        messages.success(
            request,
            "Le paiement a été validé avec succès.",
        )

    return redirect(
        "finances:detail_frais",
        frais_id=frais.pk,
    )


# ============================================================
# RESPONSABLE — ANNULER UN PAIEMENT
# ============================================================

@login_required
@require_POST
@transaction.atomic
def annuler_paiement(request, paiement_id):
    utilisateur = verifier_responsable_finances(request)

    paiement = get_object_or_404(
        Paiement.objects
        .select_for_update()
        .select_related(
            "frais_hebergement",
            "frais_hebergement__etudiant",
            "frais_hebergement__etudiant__utilisateur",
        ),
        pk=paiement_id,
    )

    frais = paiement.frais_hebergement

    motif = request.POST.get(
        "motif_annulation",
        "",
    ).strip()

    if not motif:
        messages.error(
            request,
            "Le motif de l'annulation est obligatoire.",
        )

        return redirect(
            "finances:detail_frais",
            frais_id=frais.pk,
        )

    if paiement.statut == Paiement.Statut.ANNULE:
        messages.error(
            request,
            "Ce paiement est déjà annulé.",
        )

        return redirect(
            "finances:detail_frais",
            frais_id=frais.pk,
        )

    statut_avant_annulation = paiement.statut

    try:
        paiement.annuler(motif)

    except ValidationError as erreur:
        messages.error(
            request,
            " ".join(erreur.messages),
        )

    else:
        HistoriqueAction.enregistrer_action(
            utilisateur=utilisateur,
            type_action=(
                HistoriqueAction.TypeAction.ANNULATION
            ),
            entite="Paiement",
            identifiant_entite=paiement.pk,
            description=(
                "Annulation du paiement de "
                f"{paiement.montant} DH pour "
                f"l'étudiant "
                f"{frais.etudiant.matricule}."
            ),
            request=request,
            anciennes_valeurs={
                "statut": statut_avant_annulation,
            },
            nouvelles_valeurs={
                "statut": paiement.statut,
                "motif_annulation": (
                    paiement.motif_annulation
                ),
            },
        )

        creer_notification(
            utilisateur=frais.etudiant.utilisateur,
            titre="Paiement annulé",
            message=(
                f"Votre paiement de "
                f"{paiement.montant} DH a été annulé. "
                f"Motif : {paiement.motif_annulation}"
            ),
            type_notification="PAIEMENT",
            lien="/finances/ma-situation/",
        )

        messages.success(
            request,
            "Le paiement a été annulé avec succès.",
        )

    return redirect(
        "finances:detail_frais",
        frais_id=frais.pk,
    )


# ============================================================
# ÉTUDIANT — CONSULTER SA SITUATION FINANCIÈRE
# ============================================================

@login_required
def ma_situation_financiere(request):
    profil_etudiant = obtenir_profil_etudiant(request)

    frais = (
        FraisHebergement.objects
        .filter(etudiant=profil_etudiant)
        .select_related("annee_universitaire")
        .prefetch_related("paiements")
        .order_by(
            "-annee_universitaire__date_debut"
        )
    )

    montant_total = sum(
        objet.montant_total
        for objet in frais
    )

    montant_paye = sum(
        objet.montant_paye
        for objet in frais
    )

    montant_restant = sum(
        objet.montant_restant
        for objet in frais
    )

    return render(
        request,
        "finances/etudiant/ma_situation_financiere.html",
        {
            "frais": frais,
            "montant_total": montant_total,
            "montant_paye": montant_paye,
            "montant_restant": montant_restant,
        },
    )


# ============================================================
# ÉTUDIANT — DÉTAIL DE SES FRAIS
# ============================================================


@login_required
def detail_frais_etudiant(request, frais_id):
    profil_etudiant = obtenir_profil_etudiant(request)

    frais = get_object_or_404(
        FraisHebergement.objects
        .select_related(
            "annee_universitaire",
        )
        .prefetch_related(
            "paiements",
        ),
        pk=frais_id,
        etudiant=profil_etudiant,
    )

    paiements = (
        frais.paiements
        .filter(
            statut__in={
                Paiement.Statut.EN_ATTENTE,
                Paiement.Statut.VALIDE,
                Paiement.Statut.ANNULE,
            }
        )
        .select_related(
            "enregistre_par",
        )
        .order_by(
            "-date_paiement",
            "-date_creation",
        )
    )

    montant_en_attente = (
        frais.paiements
        .filter(
            statut=Paiement.Statut.EN_ATTENTE,
        )
        .aggregate(
            total=Sum("montant")
        )["total"]
        or Decimal("0.00")
    )

    montant_declarable = max(
        frais.montant_restant
        - montant_en_attente,
        Decimal("0.00"),
    )

    pourcentage_valide = 0
    pourcentage_en_attente = 0

    if frais.montant_total > 0:
        pourcentage_valide = round(
            float(
                frais.montant_paye
                / frais.montant_total
            )
            * 100
        )

        pourcentage_en_attente = round(
            float(
                montant_en_attente
                / frais.montant_total
            )
            * 100
        )

    pourcentage_valide = max(
        0,
        min(100, pourcentage_valide),
    )

    pourcentage_en_attente = max(
        0,
        min(
            100 - pourcentage_valide,
            pourcentage_en_attente,
        ),
    )

    peut_declarer_paiement = (
        frais.est_actif
        and not frais.est_solde
        and montant_declarable > 0
    )

    return render(
        request,
        "finances/etudiant/detail_frais.html",
        {
            "frais": frais,
            "paiements": paiements,

            "montant_en_attente": montant_en_attente,
            "montant_declarable": montant_declarable,

            "pourcentage_valide": pourcentage_valide,
            "pourcentage_en_attente": (
                pourcentage_en_attente
            ),

            "peut_declarer_paiement": (
                peut_declarer_paiement
            ),
        },
    )


@login_required
@transaction.atomic
def declarer_paiement_etudiant(
    request,
    frais_id,
):
    profil_etudiant = obtenir_profil_etudiant(request)

    frais = get_object_or_404(
        FraisHebergement.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
        )
        .prefetch_related(
            "paiements",
        ),
        pk=frais_id,
        etudiant=profil_etudiant,
        est_actif=True,
    )

    if frais.est_solde:
        messages.info(
            request,
            "Ces frais sont déjà entièrement soldés.",
        )

        return redirect(
            "finances:detail_frais_etudiant",
            frais_id=frais.pk,
        )

    formulaire = DeclarationPaiementEtudiantForm(
        request.POST or None,
        request.FILES or None,
        frais_hebergement=frais,
    )

    if (
        request.method == "POST"
        and formulaire.is_valid()
    ):
        paiement = formulaire.save(
            commit=False
        )

        paiement.frais_hebergement = frais
        paiement.origine = Paiement.Origine.ETUDIANT
        paiement.enregistre_par = None
        paiement.statut = Paiement.Statut.EN_ATTENTE

        try:
            paiement.full_clean()
            paiement.save()

        except ValidationError as erreur:
            if hasattr(erreur, "message_dict"):
                for champ, erreurs in (
                    erreur.message_dict.items()
                ):
                    for message in erreurs:
                        formulaire.add_error(
                            (
                                champ
                                if champ in formulaire.fields
                                else None
                            ),
                            message,
                        )
            else:
                formulaire.add_error(
                    None,
                    " ".join(erreur.messages),
                )

        else:
            HistoriqueAction.enregistrer_action(
                utilisateur=request.user,
                type_action=(
                    HistoriqueAction
                    .TypeAction
                    .CREATION
                ),
                entite="Paiement",
                identifiant_entite=paiement.pk,
                description=(
                    "Déclaration étudiante d'un paiement "
                    f"de {paiement.montant} DH pour "
                    f"l'année "
                    f"{frais.annee_universitaire.libelle}."
                ),
                request=request,
                nouvelles_valeurs={
                    "montant": str(
                        paiement.montant
                    ),
                    "date_paiement": str(
                        paiement.date_paiement
                    ),
                    "mode_paiement": (
                        paiement.mode_paiement
                    ),
                    "reference": (
                        paiement.reference
                    ),
                    "origine": paiement.origine,
                    "statut": paiement.statut,
                },
            )

            creer_notification(
                utilisateur=request.user,
                titre="Paiement transmis",
                message=(
                    f"Votre déclaration de paiement de "
                    f"{paiement.montant} DH a été transmise. "
                    "Elle est en attente de validation."
                ),
                type_notification="PAIEMENT",
                lien=(
                    f"/finances/mes-frais/"
                    f"{frais.pk}/"
                ),
            )

            responsables = (
                Utilisateur.objects
                .filter(
                    Q(is_superuser=True)
                    | Q(
                        role__in=[
                            (
                                Utilisateur
                                .Role
                                .ADMINISTRATEUR
                            ),
                            (
                                Utilisateur
                                .Role
                                .RESPONSABLE
                            ),
                        ]
                    ),
                    is_active=True,
                )
                .exclude(pk=request.user.pk)
                .distinct()
            )

            for responsable in responsables:
                creer_notification(
                    utilisateur=responsable,
                    titre=(
                        "Nouvelle déclaration "
                        "de paiement"
                    ),
                    message=(
                        f"L'étudiant "
                        f"{frais.etudiant.matricule} "
                        f"a déclaré un paiement de "
                        f"{paiement.montant} DH."
                    ),
                    type_notification="PAIEMENT",
                    lien=(
                        f"/finances/frais/"
                        f"{frais.pk}/"
                    ),
                )

            messages.success(
                request,
                (
                    "Votre paiement a été transmis. "
                    "Il reste en attente jusqu'à sa "
                    "validation par l'administration."
                ),
            )

            return redirect(
                "finances:detail_frais_etudiant",
                frais_id=frais.pk,
            )

    return render(
        request,
        (
            "finances/etudiant/"
            "declarer_paiement.html"
        ),
        {
            "frais": frais,
            "formulaire": formulaire,
            "montant_en_attente": (
                formulaire.montant_en_attente
            ),
            "montant_declarable": (
                formulaire.montant_declarable
            ),
        },
    )

@login_required
def liste_paiements_en_attente(request):
    verifier_responsable_finances(request)

    recherche = request.GET.get("recherche", "").strip()
    origine_selectionnee = request.GET.get("origine", "").strip()

    paiements = (
        Paiement.objects
        .filter(statut=Paiement.Statut.EN_ATTENTE)
        .select_related(
            "frais_hebergement",
            "frais_hebergement__etudiant",
            "frais_hebergement__etudiant__utilisateur",
            "frais_hebergement__annee_universitaire",
            "enregistre_par",
        )
        .order_by("date_paiement", "date_creation")
    )

    if recherche:
        paiements = paiements.filter(
            Q(
                frais_hebergement__etudiant__matricule__icontains=recherche
            )
            | Q(
                frais_hebergement__etudiant__cne__icontains=recherche
            )
            | Q(
                frais_hebergement__etudiant__utilisateur__first_name__icontains=recherche
            )
            | Q(
                frais_hebergement__etudiant__utilisateur__last_name__icontains=recherche
            )
            | Q(reference__icontains=recherche)
        ).distinct()

    origines_valides = {
        valeur for valeur, _ in Paiement.Origine.choices
    }

    if (
        origine_selectionnee
        and origine_selectionnee in origines_valides
    ):
        paiements = paiements.filter(
            origine=origine_selectionnee
        )

    montant_total_en_attente = (
        paiements.aggregate(total=Sum("montant"))["total"]
        or Decimal("0.00")
    )

    return render(
        request,
        "finances/responsable/paiements_en_attente.html",
        {
            "paiements": paiements,
            "nombre_paiements": paiements.count(),
            "montant_total_en_attente": montant_total_en_attente,
            "recherche": recherche,
            "origine_selectionnee": origine_selectionnee,
            "choix_origines": Paiement.Origine.choices,
        },
    )

@login_required
def recu_paiement_etudiant(request, paiement_id):
    profil_etudiant = obtenir_profil_etudiant(request)

    paiement = get_object_or_404(
        Paiement.objects.select_related(
            "frais_hebergement",
            "frais_hebergement__etudiant",
            "frais_hebergement__etudiant__utilisateur",
            "frais_hebergement__annee_universitaire",
            "enregistre_par",
        ),
        pk=paiement_id,
        statut=Paiement.Statut.VALIDE,
        frais_hebergement__etudiant=profil_etudiant,
    )

    frais = paiement.frais_hebergement
    date_reference = paiement.date_validation or paiement.date_creation
    numero_recu = f"REC-{date_reference:%Y%m%d}-{paiement.pk:06d}"

    return render(
        request,
        "finances/etudiant/recu_paiement.html",
        {
            "paiement": paiement,
            "frais": frais,
            "numero_recu": numero_recu,
        },
    )

@login_required
def recu_paiement_responsable(
    request,
    paiement_id,
):
    verifier_responsable_finances(request)

    paiement = get_object_or_404(
        Paiement.objects.select_related(
            "frais_hebergement",
            "frais_hebergement__etudiant",
            "frais_hebergement__etudiant__utilisateur",
            "frais_hebergement__annee_universitaire",
            "enregistre_par",
        ),
        pk=paiement_id,
        statut=Paiement.Statut.VALIDE,
    )

    frais = paiement.frais_hebergement

    date_reference = (
        paiement.date_validation
        or paiement.date_creation
    )

    numero_recu = (
        f"REC-"
        f"{date_reference:%Y%m%d}-"
        f"{paiement.pk:06d}"
    )

    return render(
        request,
        "finances/responsable/recu_paiement.html",
        {
            "paiement": paiement,
            "frais": frais,
            "numero_recu": numero_recu,
        },
    )
