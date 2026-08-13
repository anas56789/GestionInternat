from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.security import obtenir_profil_etudiant
from accounts.models import Utilisateur
from audit.models import HistoriqueAction
from notifications.models import (
    Notification,
    creer_notification,
)
from .forms import (
    AffectationForm,
    DemandeHebergementForm,
    JustificatifFormSet,
    TransfertEtudiantForm,
    BatimentForm,
    ChambreForm,
    AnneeUniversitaireForm,
)
from .models import (
    Affectation,
    AnneeUniversitaire,
    Batiment,
    Chambre,
    DemandeHebergement,
    Transfert,
    transferer_etudiant,
    Justificatif
)
from django.core.paginator import Paginator

# ============================================================
# CONTRÔLE D'ACCÈS — RESPONSABLE ET ADMINISTRATEUR
# ============================================================

def verifier_responsable(request):
    """
    Autorise uniquement :
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
            "Vous n'êtes pas autorisé à gérer l'hébergement."
        )

    return utilisateur


# ============================================================
# ÉTUDIANT — DÉPOSER UNE DEMANDE
# ============================================================

@login_required
@transaction.atomic
def deposer_demande(request):
    profil = obtenir_profil_etudiant(request)

    if request.method == "POST":
        formulaire = DemandeHebergementForm(
            request.POST,
            etudiant=profil,
        )

        justificatifs_formset = JustificatifFormSet(
            request.POST,
            request.FILES,
            prefix="justificatifs",
        )

        action = request.POST.get(
            "action",
            "brouillon",
        )

        formulaire_valide = formulaire.is_valid()
        justificatifs_valides = (
            justificatifs_formset.is_valid()
        )

        if formulaire_valide and justificatifs_valides:
            demande = formulaire.save(commit=False)

            demande.etudiant = profil

            if action == "soumettre":
                demande.statut = (
                    DemandeHebergement.Statut.SOUMISE
                )
                demande.date_soumission = timezone.now()
            else:
                demande.statut = (
                    DemandeHebergement.Statut.BROUILLON
                )
                demande.date_soumission = None

            demande.save()

            justificatifs_formset.instance = demande
            justificatifs_formset.save()

            if action == "soumettre":
                messages.success(
                    request,
                    (
                        "Votre demande a été soumise "
                        "avec succès."
                    ),
                )
            else:
                messages.success(
                    request,
                    (
                        "Votre demande a été enregistrée "
                        "en brouillon."
                    ),
                )

            return redirect(
                "hebergement:mes_demandes"
            )

        messages.error(
            request,
            (
                "La demande n'a pas été enregistrée. "
                "Corrigez les erreurs indiquées."
            ),
        )

    else:
        formulaire = DemandeHebergementForm(
            etudiant=profil,
        )

        justificatifs_formset = JustificatifFormSet(
            prefix="justificatifs",
        )

    return render(
        request,
        "hebergement/etudiant/formulaire_demande.html",
        {
            "formulaire": formulaire,
            "justificatifs_formset": (
                justificatifs_formset
            ),
        },
    )


# ============================================================
# ÉTUDIANT — MODIFIER UNE DEMANDE
# ============================================================

@login_required
def modifier_demande(request, demande_id):
    profil = obtenir_profil_etudiant(request)

    demande = get_object_or_404(
    DemandeHebergement,
    pk=demande_id,
    etudiant=profil,
    )

    if demande.statut not in {
        DemandeHebergement.Statut.BROUILLON,
        DemandeHebergement.Statut.INCOMPLETE,
    }:
        messages.error(
            request,
            "Cette demande ne peut plus être modifiée.",
        )

        return redirect(
            "accounts:espace_etudiant"
        )

    if request.method == "POST":
        formulaire = DemandeHebergementForm(
            request.POST,
            instance=demande,
            etudiant=profil,
        )

        justificatifs = JustificatifFormSet(
            request.POST,
            request.FILES,
            instance=demande,
            prefix="justificatifs",
        )

        action = request.POST.get(
            "action",
            "brouillon",
        )

        if formulaire.is_valid() and justificatifs.is_valid():
            with transaction.atomic():
                demande = formulaire.save(commit=False)

                if action == "soumettre":
                    demande.statut = (
                        DemandeHebergement.Statut.SOUMISE
                    )

                    demande.date_soumission = timezone.now()

                else:
                    demande.statut = (
                        DemandeHebergement.Statut.BROUILLON
                    )

                    demande.date_soumission = None

                demande.save()
                justificatifs.save()

            if action == "soumettre":
                messages.success(
                    request,
                    "Votre demande a été soumise.",
                )

            else:
                messages.success(
                    request,
                    "Votre brouillon a été mis à jour.",
                )

            return redirect(
                "accounts:espace_etudiant"
            )

    else:
        formulaire = DemandeHebergementForm(
            instance=demande,
            etudiant=profil,
        )

        justificatifs = JustificatifFormSet(
            instance=demande,
            prefix="justificatifs",
        )

    return render(
    request,
    "hebergement/etudiant/formulaire_demande.html",
    {
        "formulaire": formulaire,
        "justificatifs_formset": justificatifs,
        "demande": demande,
    },
)


# ============================================================
# ÉTUDIANT — LISTE DE SES DEMANDES
# ============================================================

@login_required
def mes_demandes(request):
    profil = obtenir_profil_etudiant(request)

    affectations_en_cours = (
        Affectation.objects
        .filter(
            etudiant=profil,
        )
        .select_related(
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
        )
        .order_by(
            "-date_creation",
        )
    )

    demandes = list(
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
            Prefetch(
                "affectations",
                queryset=affectations_en_cours,
                to_attr="affectations_en_cours",
            ),
        )
        .order_by(
            "-date_creation",
        )
    )

    for demande in demandes:
        justificatifs = list(
            demande.justificatifs.all()
        )

        demande.nombre_justificatifs = len(
            justificatifs
        )

        demande.nombre_justificatifs_valides = sum(
            1
            for justificatif in justificatifs
            if justificatif.statut_validation
            == Justificatif.StatutValidation.VALIDE
        )

        demande.nombre_justificatifs_en_attente = sum(
            1
            for justificatif in justificatifs
            if justificatif.statut_validation
            == Justificatif.StatutValidation.EN_ATTENTE
        )

        demande.nombre_justificatifs_rejetes = sum(
            1
            for justificatif in justificatifs
            if justificatif.statut_validation
            == Justificatif.StatutValidation.REJETE
        )

        demande.tous_justificatifs_valides = (
            demande.nombre_justificatifs > 0
            and demande.nombre_justificatifs_valides
            == demande.nombre_justificatifs
        )

        demande.affectation_en_cours = (
            demande.affectations_en_cours[0]
            if demande.affectations_en_cours
            else None
        )

    nombre_total = len(
        demandes
    )

    nombre_brouillons = sum(
        1
        for demande in demandes
        if demande.statut
        == DemandeHebergement.Statut.BROUILLON
    )

    nombre_en_cours = sum(
        1
        for demande in demandes
        if demande.statut
        in {
            DemandeHebergement.Statut.SOUMISE,
            DemandeHebergement.Statut.EN_ETUDE,
        }
    )

    nombre_acceptees = sum(
        1
        for demande in demandes
        if demande.statut
        == DemandeHebergement.Statut.ACCEPTEE
    )

    nombre_refusees = sum(
        1
        for demande in demandes
        if demande.statut
        == DemandeHebergement.Statut.REFUSEE
    )

    contexte = {
        "demandes": demandes,
        "nombre_total": nombre_total,
        "nombre_brouillons": nombre_brouillons,
        "nombre_en_cours": nombre_en_cours,
        "nombre_acceptees": nombre_acceptees,
        "nombre_refusees": nombre_refusees,
    }

    return render(
        request,
        "hebergement/mes_demandes.html",
        contexte,
    )

# ============================================================
# RESPONSABLE — DÉTAIL D'UNE DEMANDE
# ============================================================

@login_required
def detail_demande_responsable(
    request,
    demande_id,
):
    verifier_responsable(request)

    demande = get_object_or_404(
        DemandeHebergement.objects.select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
            "traitee_par",
        ),
        pk=demande_id,
    )

    justificatifs = list(
        Justificatif.objects
        .filter(
            demande=demande,
        )
        .order_by(
            "type_document",
            "-date_ajout",
        )
    )

    # --------------------------------------------------------
    # STATISTIQUES GÉNÉRALES DES JUSTIFICATIFS
    # --------------------------------------------------------

    nombre_justificatifs = len(
        justificatifs
    )

    nombre_justificatifs_en_attente = sum(
        1
        for justificatif in justificatifs
        if justificatif.statut_validation
        == Justificatif.StatutValidation.EN_ATTENTE
    )

    nombre_justificatifs_valides = sum(
        1
        for justificatif in justificatifs
        if justificatif.statut_validation
        == Justificatif.StatutValidation.VALIDE
    )

    nombre_justificatifs_rejetes = sum(
        1
        for justificatif in justificatifs
        if justificatif.statut_validation
        == Justificatif.StatutValidation.REJETE
    )

    tous_les_justificatifs_valides = (
        nombre_justificatifs > 0
        and nombre_justificatifs_valides
        == nombre_justificatifs
    )

    # --------------------------------------------------------
    # PIÈCES OBLIGATOIRES
    # --------------------------------------------------------

    types_obligatoires = {
        Justificatif.TypeDocument.CIN,
        Justificatif.TypeDocument.CERTIFICAT_INSCRIPTION,
        Justificatif.TypeDocument.JUSTIFICATIF_DOMICILE,
        Justificatif.TypeDocument.JUSTIFICATIF_SOCIAL,
    }

    libelles_types = dict(
        Justificatif.TypeDocument.choices
    )

    documents_par_type = {}

    for justificatif in justificatifs:
        documents_par_type.setdefault(
            justificatif.type_document,
            [],
        ).append(
            justificatif
        )

    etat_documents_obligatoires = []
    documents_manquants = []

    for type_document in sorted(
        types_obligatoires
    ):
        documents_type = documents_par_type.get(
            type_document,
            [],
        )

        present = bool(
            documents_type
        )

        en_attente = any(
            document.statut_validation
            == Justificatif.StatutValidation.EN_ATTENTE
            for document in documents_type
        )

        rejete = any(
            document.statut_validation
            == Justificatif.StatutValidation.REJETE
            for document in documents_type
        )

        valide = (
            present
            and not en_attente
            and not rejete
            and all(
                document.statut_validation
                == Justificatif.StatutValidation.VALIDE
                for document in documents_type
            )
        )

        libelle = libelles_types.get(
            type_document,
            type_document,
        )

        if not present:
            documents_manquants.append(
                libelle
            )

        etat_documents_obligatoires.append(
            {
                "code": type_document,
                "libelle": libelle,
                "present": present,
                "en_attente": en_attente,
                "rejete": rejete,
                "valide": valide,
            }
        )

    documents_obligatoires_valides = all(
        document["valide"]
        for document
        in etat_documents_obligatoires
    )

    # --------------------------------------------------------
    # ÉTAT DE TRAITEMENT
    # --------------------------------------------------------

    statuts_traitables = {
        DemandeHebergement.Statut.SOUMISE,
        DemandeHebergement.Statut.EN_ETUDE,
    }

    demande_traitable = (
        demande.statut
        in statuts_traitables
    )

    demande_peut_etre_acceptee = (
        demande_traitable
        and not documents_manquants
        and documents_obligatoires_valides
    )

    contexte = {
        "demande": demande,
        "justificatifs": justificatifs,

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
        "tous_les_justificatifs_valides": (
            tous_les_justificatifs_valides
        ),

        "etat_documents_obligatoires": (
            etat_documents_obligatoires
        ),
        "documents_manquants": (
            documents_manquants
        ),
        "documents_obligatoires_valides": (
            documents_obligatoires_valides
        ),

        "demande_traitable": (
            demande_traitable
        ),
        "demande_peut_etre_acceptee": (
            demande_peut_etre_acceptee
        ),
    }

    return render(
        request,
        "hebergement/responsable/detail_demande.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — LISTE DES DEMANDES
# ============================================================

@login_required
def liste_demandes_responsable(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    annee_selectionnee = request.GET.get(
        "annee",
        "",
    ).strip()

    date_debut = request.GET.get(
        "date_debut",
        "",
    ).strip()

    date_fin = request.GET.get(
        "date_fin",
        "",
    ).strip()

    demandes = (
        DemandeHebergement.objects
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
            "traitee_par",
        )
        .prefetch_related(
            "justificatifs",
        )
        .order_by(
            "-date_creation",
        )
    )

    # ========================================================
    # RECHERCHE TEXTUELLE
    # ========================================================

    if recherche:
        demandes = demandes.filter(
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
            | Q(
                etudiant__filiere__icontains=recherche
            )
            | Q(
                motif__icontains=recherche
            )
        ).distinct()

    # ========================================================
    # FILTRE PAR STATUT
    # ========================================================

    statuts_valides = {
        valeur
        for valeur, _ in DemandeHebergement.Statut.choices
    }

    if (
        statut_selectionne
        and statut_selectionne in statuts_valides
    ):
        demandes = demandes.filter(
            statut=statut_selectionne,
        )

    # ========================================================
    # FILTRE PAR ANNÉE UNIVERSITAIRE
    # ========================================================

    if annee_selectionnee.isdigit():
        demandes = demandes.filter(
            annee_universitaire_id=int(
                annee_selectionnee
            ),
        )

    # ========================================================
    # FILTRE PAR DATES
    # ========================================================

    date_debut_valide = None
    date_fin_valide = None

    if date_debut:
        try:
            date_debut_valide = datetime.strptime(
                date_debut,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            messages.error(
                request,
                "La date de début est invalide.",
            )

    if date_fin:
        try:
            date_fin_valide = datetime.strptime(
                date_fin,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            messages.error(
                request,
                "La date de fin est invalide.",
            )

    if (
        date_debut_valide
        and date_fin_valide
        and date_fin_valide < date_debut_valide
    ):
        messages.error(
            request,
            (
                "La date de fin ne peut pas être "
                "antérieure à la date de début."
            ),
        )

    else:
        if date_debut_valide:
            demandes = demandes.filter(
                date_creation__date__gte=(
                    date_debut_valide
                ),
            )

        if date_fin_valide:
            demandes = demandes.filter(
                date_creation__date__lte=(
                    date_fin_valide
                ),
            )

    # ========================================================
    # COMPTEURS GLOBAUX
    # ========================================================

    demandes_globales = (
        DemandeHebergement.objects.all()
    )

    nombre_total_global = (
        demandes_globales.count()
    )

    nombre_brouillons = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.BROUILLON,
        )
        .count()
    )

    nombre_soumises = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.SOUMISE,
        )
        .count()
    )

    nombre_en_etude = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.EN_ETUDE,
        )
        .count()
    )

    nombre_incompletes = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.INCOMPLETE,
        )
        .count()
    )

    nombre_acceptees = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.ACCEPTEE,
        )
        .count()
    )

    nombre_refusees = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.REFUSEE,
        )
        .count()
    )

    nombre_attente = (
        demandes_globales
        .filter(
            statut=DemandeHebergement.Statut.LISTE_ATTENTE,
        )
        .count()
    )

    # ========================================================
    # ANNÉES DISPONIBLES
    # ========================================================

    annees_universitaires = (
        AnneeUniversitaire.objects
        .all()
        .order_by(
            "-date_debut",
        )
    )

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        demandes,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    parametres_filtres = request.GET.copy()

    parametres_filtres.pop(
        "page",
        None,
    )

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "demandes": page_obj,
        "page_obj": page_obj,

        "recherche": recherche,
        "statut_selectionne": statut_selectionne,
        "annee_selectionnee": annee_selectionnee,
        "date_debut": date_debut,
        "date_fin": date_fin,

        "choix_statuts": (
            DemandeHebergement.Statut.choices
        ),
        "annees_universitaires": (
            annees_universitaires
        ),

        "nombre_demandes": paginator.count,
        "nombre_total_global": nombre_total_global,
        "nombre_brouillons": nombre_brouillons,
        "nombre_soumises": nombre_soumises,
        "nombre_en_etude": nombre_en_etude,
        "nombre_incompletes": nombre_incompletes,
        "nombre_acceptees": nombre_acceptees,
        "nombre_refusees": nombre_refusees,
        "nombre_attente": nombre_attente,

        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        (
            "hebergement/responsable/"
            "liste_demandes.html"
        ),
        contexte,
    )


# ============================================================
# ÉTUDIANT — DÉTAIL D'UNE DEMANDE
# ============================================================


@login_required
def detail_demande(request, demande_id):
    profil = obtenir_profil_etudiant(request)

    demande = get_object_or_404(
        DemandeHebergement.objects
        .select_related(
            "annee_universitaire",
            "traitee_par",
        )
        .prefetch_related(
            "justificatifs",
        ),
        pk=demande_id,
        etudiant=profil,
    )

    justificatifs = list(
        demande.justificatifs
        .all()
        .order_by(
            "type_document",
            "-date_ajout",
        )
    )

    nombre_justificatifs = len(
        justificatifs
    )

    nombre_justificatifs_en_attente = sum(
        1
        for justificatif in justificatifs
        if justificatif.statut_validation
        == Justificatif.StatutValidation.EN_ATTENTE
    )

    nombre_justificatifs_valides = sum(
        1
        for justificatif in justificatifs
        if justificatif.statut_validation
        == Justificatif.StatutValidation.VALIDE
    )

    nombre_justificatifs_rejetes = sum(
        1
        for justificatif in justificatifs
        if justificatif.statut_validation
        == Justificatif.StatutValidation.REJETE
    )

    tous_les_justificatifs_valides = (
        nombre_justificatifs > 0
        and nombre_justificatifs_valides
        == nombre_justificatifs
    )

    affectations = list(
        Affectation.objects
        .filter(
            demande_hebergement=demande,
        )
        .select_related(
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
            "creee_par",
        )
        .order_by(
            "-date_creation",
        )
    )

    affectation_active = next(
        (
            affectation
            for affectation in affectations
            if affectation.statut
            in {
                Affectation.Statut.PREVUE,
                Affectation.Statut.ACTIVE,
            }
        ),
        None,
    )

    derniere_affectation = (
        affectations[0]
        if affectations
        else None
    )

    contexte = {
        "demande": demande,
        "justificatifs": justificatifs,

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
        "tous_les_justificatifs_valides": (
            tous_les_justificatifs_valides
        ),

        "affectations": affectations,
        "affectation_active": affectation_active,
        "derniere_affectation": (
            derniere_affectation
        ),
        "nombre_affectations": len(
            affectations
        ),
    }

    return render(
        request,
        "hebergement/detail_demande.html",
        contexte,
    )



# ============================================================
# RESPONSABLE — TRAITER UNE DEMANDE
# ============================================================

@login_required
@transaction.atomic
def traiter_demande(request, demande_id):
    utilisateur = verifier_responsable(
        request
    )

    demande = get_object_or_404(
        DemandeHebergement.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
            "traitee_par",
        ),
        pk=demande_id,
    )

    url_detail = (
        "hebergement:detail_demande_responsable"
    )

    if request.method != "POST":
        messages.error(
            request,
            (
                "Le traitement d'une demande doit être "
                "effectué depuis le formulaire prévu."
            ),
        )

        return redirect(
            url_detail,
            demande_id=demande.pk,
        )

    action = request.POST.get(
        "action",
        "",
    ).strip()

    motif_decision = request.POST.get(
        "motif_decision",
        "",
    ).strip()

    # --------------------------------------------------------
    # TRANSITIONS AUTORISÉES
    # --------------------------------------------------------

    transitions_autorisees = {
        "mettre_en_etude": {
            DemandeHebergement.Statut.SOUMISE,
        },
        "incomplete": {
            DemandeHebergement.Statut.SOUMISE,
            DemandeHebergement.Statut.EN_ETUDE,
        },
        "accepter": {
            DemandeHebergement.Statut.SOUMISE,
            DemandeHebergement.Statut.EN_ETUDE,
        },
        "refuser": {
            DemandeHebergement.Statut.SOUMISE,
            DemandeHebergement.Statut.EN_ETUDE,
        },
        "liste_attente": {
            DemandeHebergement.Statut.SOUMISE,
            DemandeHebergement.Statut.EN_ETUDE,
        },
    }

    if action not in transitions_autorisees:
        messages.error(
            request,
            "L'action demandée est invalide.",
        )

        return redirect(
            url_detail,
            demande_id=demande.pk,
        )

    if (
        demande.statut
        not in transitions_autorisees[
            action
        ]
    ):
        messages.error(
            request,
            (
                "Cette action n'est pas autorisée "
                "pour le statut actuel de la demande."
            ),
        )

        return redirect(
            url_detail,
            demande_id=demande.pk,
        )

    # --------------------------------------------------------
    # MOTIF OBLIGATOIRE
    # --------------------------------------------------------

    actions_avec_motif = {
        "incomplete",
        "refuser",
        "liste_attente",
    }

    if (
        action in actions_avec_motif
        and not motif_decision
    ):
        messages.error(
            request,
            "Le motif est obligatoire pour cette décision.",
        )

        return redirect(
            url_detail,
            demande_id=demande.pk,
        )

    if len(motif_decision) > 1000:
        messages.error(
            request,
            (
                "Le motif de décision ne peut pas "
                "dépasser 1 000 caractères."
            ),
        )

        return redirect(
            url_detail,
            demande_id=demande.pk,
        )

    # --------------------------------------------------------
    # CONTRÔLE DES PIÈCES AVANT ACCEPTATION
    # --------------------------------------------------------

    if action == "accepter":

        justificatifs = list(
            Justificatif.objects
            .select_for_update()
            .filter(
                demande=demande,
            )
        )

        types_obligatoires = {
            Justificatif.TypeDocument.CIN,
            Justificatif.TypeDocument.CERTIFICAT_INSCRIPTION,
            Justificatif.TypeDocument.JUSTIFICATIF_DOMICILE,
            Justificatif.TypeDocument.JUSTIFICATIF_SOCIAL,
        }

        types_presents = {
            justificatif.type_document
            for justificatif
            in justificatifs
        }

        types_manquants = (
            types_obligatoires
            - types_presents
        )

        if types_manquants:

            libelles = dict(
                Justificatif.TypeDocument.choices
            )

            libelles_manquants = [
                libelles.get(
                    type_document,
                    type_document,
                )
                for type_document
                in sorted(
                    types_manquants
                )
            ]

            messages.error(
                request,
                (
                    "La demande ne peut pas être acceptée. "
                    "Documents manquants : "
                    + ", ".join(
                        libelles_manquants
                    )
                    + "."
                ),
            )

            return redirect(
                url_detail,
                demande_id=demande.pk,
            )

        justificatifs_obligatoires = [
            justificatif
            for justificatif
            in justificatifs
            if justificatif.type_document
            in types_obligatoires
        ]

        justificatifs_rejetes = [
            justificatif
            for justificatif
            in justificatifs_obligatoires
            if justificatif.statut_validation
            == Justificatif.StatutValidation.REJETE
        ]

        if justificatifs_rejetes:
            messages.error(
                request,
                (
                    "La demande ne peut pas être acceptée : "
                    "au moins une pièce obligatoire est rejetée."
                ),
            )

            return redirect(
                url_detail,
                demande_id=demande.pk,
            )

        justificatifs_en_attente = [
            justificatif
            for justificatif
            in justificatifs_obligatoires
            if justificatif.statut_validation
            == Justificatif.StatutValidation.EN_ATTENTE
        ]

        if justificatifs_en_attente:
            messages.error(
                request,
                (
                    "Certains documents obligatoires sont "
                    "encore en attente de validation."
                ),
            )

            return redirect(
                url_detail,
                demande_id=demande.pk,
            )

        tous_obligatoires_valides = all(
            justificatif.statut_validation
            == Justificatif.StatutValidation.VALIDE
            for justificatif
            in justificatifs_obligatoires
        )

        if not tous_obligatoires_valides:
            messages.error(
                request,
                (
                    "Toutes les pièces obligatoires doivent "
                    "être validées avant l'acceptation."
                ),
            )

            return redirect(
                url_detail,
                demande_id=demande.pk,
            )

    # --------------------------------------------------------
    # NOUVEAU STATUT
    # --------------------------------------------------------

    nouveaux_statuts = {
        "mettre_en_etude": (
            DemandeHebergement.Statut.EN_ETUDE
        ),
        "incomplete": (
            DemandeHebergement.Statut.INCOMPLETE
        ),
        "accepter": (
            DemandeHebergement.Statut.ACCEPTEE
        ),
        "refuser": (
            DemandeHebergement.Statut.REFUSEE
        ),
        "liste_attente": (
            DemandeHebergement.Statut.LISTE_ATTENTE
        ),
    }

    messages_succes = {
        "mettre_en_etude": (
            "La demande est maintenant en cours d'étude."
        ),
        "incomplete": (
            "La demande a été déclarée incomplète."
        ),
        "accepter": (
            "La demande d'hébergement a été acceptée."
        ),
        "refuser": (
            "La demande d'hébergement a été refusée."
        ),
        "liste_attente": (
            "La demande a été placée sur la liste d'attente."
        ),
    }

    ancien_statut = demande.statut
    ancien_motif = demande.motif_decision
    ancienne_personne_traitante = (
        demande.traitee_par_id
    )
    ancienne_date_decision = (
        demande.date_decision
    )

    demande.statut = (
        nouveaux_statuts[
            action
        ]
    )

    demande.traitee_par = (
        utilisateur
    )

    if action == "mettre_en_etude":
        demande.motif_decision = ""
        demande.date_decision = None
    else:
        demande.motif_decision = (
            motif_decision
        )
        demande.date_decision = (
            timezone.now()
        )

    try:
        demande.full_clean()
        demande.save()

    except ValidationError as erreur:

        if hasattr(
            erreur,
            "message_dict",
        ):
            erreurs = []

            for liste_erreurs in (
                erreur.message_dict.values()
            ):
                erreurs.extend(
                    liste_erreurs
                )

            message_erreur = " ".join(
                erreurs
            )

        else:
            message_erreur = " ".join(
                erreur.messages
            )

        messages.error(
            request,
            message_erreur,
        )

        transaction.set_rollback(
            True
        )

        return redirect(
            url_detail,
            demande_id=demande.pk,
        )

    # --------------------------------------------------------
    # AUDIT
    # --------------------------------------------------------

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.TRAITEMENT
        ),
        entite="DemandeHebergement",
        identifiant_entite=demande.pk,
        description=(
            "Traitement de la demande d'hébergement "
            f"de l'étudiant "
            f"{demande.etudiant.matricule} : "
            f"{demande.get_statut_display()}."
        ),
        request=request,
        anciennes_valeurs={
            "statut": ancien_statut,
            "motif_decision": ancien_motif,
            "traitee_par": (
                ancienne_personne_traitante
            ),
            "date_decision": (
                str(
                    ancienne_date_decision
                )
                if ancienne_date_decision
                else None
            ),
        },
        nouvelles_valeurs={
            "statut": demande.statut,
            "motif_decision": (
                demande.motif_decision
            ),
            "traitee_par": (
                utilisateur.pk
            ),
            "date_decision": (
                str(
                    demande.date_decision
                )
                if demande.date_decision
                else None
            ),
        },
    )

    # --------------------------------------------------------
    # NOTIFICATION ÉTUDIANT
    # --------------------------------------------------------

    titres_notifications = {
        DemandeHebergement.Statut.EN_ETUDE: (
            "Demande en cours d'étude"
        ),
        DemandeHebergement.Statut.INCOMPLETE: (
            "Demande incomplète"
        ),
        DemandeHebergement.Statut.ACCEPTEE: (
            "Demande d'hébergement acceptée"
        ),
        DemandeHebergement.Statut.REFUSEE: (
            "Demande d'hébergement refusée"
        ),
        DemandeHebergement.Statut.LISTE_ATTENTE: (
            "Demande placée en liste d'attente"
        ),
    }

    if (
        demande.statut
        == DemandeHebergement.Statut.EN_ETUDE
    ):
        message_notification = (
            "Votre demande d'hébergement est "
            "maintenant en cours d'étude."
        )

    elif (
        demande.statut
        == DemandeHebergement.Statut.INCOMPLETE
    ):
        message_notification = (
            "Votre demande d'hébergement a été "
            "déclarée incomplète. "
            f"Motif : {motif_decision}"
        )

    elif (
        demande.statut
        == DemandeHebergement.Statut.ACCEPTEE
    ):
        message_notification = (
            "Votre demande d'hébergement pour l'année "
            f"{demande.annee_universitaire.libelle} "
            "a été acceptée."
        )

    elif (
        demande.statut
        == DemandeHebergement.Statut.REFUSEE
    ):
        message_notification = (
            "Votre demande d'hébergement a été refusée. "
            f"Motif : {motif_decision}"
        )

    else:
        message_notification = (
            "Votre demande d'hébergement a été placée "
            "sur la liste d'attente. "
            f"Motif : {motif_decision}"
        )

    creer_notification(
        utilisateur=(
            demande.etudiant.utilisateur
        ),
        titre=(
            titres_notifications[
                demande.statut
            ]
        ),
        message=(
            message_notification
        ),
        type_notification="DEMANDE",
        lien=(
            f"/hebergement/demande/"
            f"{demande.pk}/"
        ),
    )

    messages.success(
        request,
        messages_succes[
            action
        ],
    )

    return redirect(
        url_detail,
        demande_id=demande.pk,
    )



# ============================================================
# RESPONSABLE — DEMANDES ACCEPTÉES À AFFECTER
# ============================================================

@login_required
def liste_demandes_a_affecter(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    etat_selectionne = request.GET.get(
        "etat",
        "TOUTES",
    ).strip().upper()

    etats_valides = {
        "TOUTES",
        "A_AFFECTER",
        "DEJA_AFFECTEES",
    }

    if etat_selectionne not in etats_valides:
        etat_selectionne = "TOUTES"

    affectations_en_cours_queryset = (
        Affectation.objects
        .filter(
            statut__in={
                Affectation.Statut.PREVUE,
                Affectation.Statut.ACTIVE,
            }
        )
        .select_related(
            "chambre",
            "chambre__batiment",
            "creee_par",
        )
        .order_by("-date_creation")
    )

    demandes_queryset = (
        DemandeHebergement.objects
        .filter(
            statut=DemandeHebergement.Statut.ACCEPTEE,
        )
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
            "traitee_par",
        )
        .prefetch_related(
            Prefetch(
                "affectations",
                queryset=affectations_en_cours_queryset,
                to_attr="affectations_en_cours",
            )
        )
        .order_by(
            "-date_decision",
            "-date_creation",
        )
    )

    if recherche:
        demandes_queryset = demandes_queryset.filter(
            Q(
                etudiant__matricule__icontains=recherche
            )
            | Q(
                etudiant__cne__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__username__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__first_name__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__last_name__icontains=recherche
            )
            | Q(
                annee_universitaire__libelle__icontains=recherche
            )
        ).distinct()

    toutes_les_demandes = list(
        demandes_queryset
    )

    for demande in toutes_les_demandes:
        if demande.affectations_en_cours:
            demande.affectation_en_cours = (
                demande.affectations_en_cours[0]
            )
            demande.est_deja_affectee = True
        else:
            demande.affectation_en_cours = None
            demande.est_deja_affectee = False

    nombre_total = len(toutes_les_demandes)

    nombre_a_affecter = sum(
        1
        for demande in toutes_les_demandes
        if not demande.est_deja_affectee
    )

    nombre_deja_affectees = sum(
        1
        for demande in toutes_les_demandes
        if demande.est_deja_affectee
    )

    if etat_selectionne == "A_AFFECTER":
        demandes_affichees = [
            demande
            for demande in toutes_les_demandes
            if not demande.est_deja_affectee
        ]

    elif etat_selectionne == "DEJA_AFFECTEES":
        demandes_affichees = [
            demande
            for demande in toutes_les_demandes
            if demande.est_deja_affectee
        ]

    else:
        demandes_affichees = toutes_les_demandes

    contexte = {
        "demandes": demandes_affichees,
        "recherche": recherche,
        "etat_selectionne": etat_selectionne,
        "nombre_total": nombre_total,
        "nombre_a_affecter": nombre_a_affecter,
        "nombre_deja_affectees": (
            nombre_deja_affectees
        ),
        "nombre_affiche": len(
            demandes_affichees
        ),
    }

    return render(
        request,
        "hebergement/responsable/liste_affectations.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — CRÉER UNE AFFECTATION
# ============================================================

@login_required
@transaction.atomic
def creer_affectation(request, demande_id):
    utilisateur = verifier_responsable(request)

    demande = get_object_or_404(
        DemandeHebergement.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "annee_universitaire",
        ),
        pk=demande_id,
        statut=DemandeHebergement.Statut.ACCEPTEE,
    )

    statuts_ouverts = {
        Affectation.Statut.PREVUE,
        Affectation.Statut.ACTIVE,
    }

    # ========================================================
    # VÉRIFIER LA DEMANDE
    # ========================================================

    affectation_demande_existante = (
        Affectation.objects
        .filter(
            demande_hebergement=demande,
            statut__in=statuts_ouverts,
        )
        .exists()
    )

    if affectation_demande_existante:
        messages.error(
            request,
            (
                "Cette demande possède déjà une affectation "
                "prévue ou active."
            ),
        )

        return redirect(
            "hebergement:liste_demandes_a_affecter"
        )

    # ========================================================
    # VÉRIFIER L’ÉTUDIANT
    # ========================================================

    affectation_etudiant_existante = (
        Affectation.objects
        .filter(
            etudiant=demande.etudiant,
            statut__in=statuts_ouverts,
        )
        .exists()
    )

    if affectation_etudiant_existante:
        messages.error(
            request,
            (
                "Cet étudiant possède déjà une affectation "
                "prévue ou active."
            ),
        )

        return redirect(
            "hebergement:liste_demandes_a_affecter"
        )

    # ========================================================
    # TRAITEMENT DU FORMULAIRE
    # ========================================================

    if request.method == "POST":
        formulaire = AffectationForm(
            request.POST,
        )

        if formulaire.is_valid():
            chambre_selectionnee = (
                formulaire.cleaned_data["chambre"]
            )

            # Verrouillage de la chambre pour empêcher deux
            # affectations simultanées sur la dernière place.
            chambre_verrouillee = get_object_or_404(
                Chambre.objects
                .select_for_update()
                .select_related(
                    "batiment",
                ),
                pk=chambre_selectionnee.pk,
            )

            affectation = formulaire.save(
                commit=False
            )

            affectation.etudiant = (
                demande.etudiant
            )

            affectation.chambre = (
                chambre_verrouillee
            )

            affectation.annee_universitaire = (
                demande.annee_universitaire
            )

            affectation.demande_hebergement = (
                demande
            )

            affectation.creee_par = (
                utilisateur
            )

            affectation.statut = (
                Affectation.Statut.PREVUE
            )

            try:
                # save() appelle déjà full_clean()
                # dans la version corrigée du modèle.
                affectation.save()

            except ValidationError as erreur:
                if hasattr(
                    erreur,
                    "message_dict",
                ):
                    for champ, erreurs in (
                        erreur.message_dict.items()
                    ):
                        champ_formulaire = (
                            champ
                            if champ in formulaire.fields
                            else None
                        )

                        for message in erreurs:
                            formulaire.add_error(
                                champ_formulaire,
                                message,
                            )

                else:
                    formulaire.add_error(
                        None,
                        " ".join(
                            erreur.messages
                        ),
                    )

            else:
                # ============================================
                # HISTORIQUE
                # ============================================

                HistoriqueAction.enregistrer_action(
                    utilisateur=utilisateur,
                    type_action=(
                        HistoriqueAction
                        .TypeAction
                        .AFFECTATION
                    ),
                    entite="Affectation",
                    identifiant_entite=affectation.pk,
                    description=(
                        "Affectation de l’étudiant "
                        f"{affectation.etudiant.matricule} "
                        "à la chambre "
                        f"{affectation.chambre.numero} "
                        "du bâtiment "
                        f"{affectation.chambre.batiment.code}."
                    ),
                    request=request,
                    nouvelles_valeurs={
                        "etudiant": (
                            affectation.etudiant.matricule
                        ),
                        "batiment": (
                            affectation
                            .chambre
                            .batiment
                            .code
                        ),
                        "chambre": (
                            affectation.chambre.numero
                        ),
                        "statut": (
                            affectation.statut
                        ),
                        "date_entree_prevue": str(
                            affectation.date_entree_prevue
                        ),
                        "date_sortie_prevue": str(
                            affectation.date_sortie_prevue
                        ),
                    },
                )

                # ============================================
                # NOTIFICATION
                # ============================================

                creer_notification(
                    utilisateur=(
                        affectation
                        .etudiant
                        .utilisateur
                    ),
                    titre="Nouvelle affectation",
                    message=(
                        "Une chambre vous a été attribuée : "
                        f"{affectation.chambre.batiment.code}/"
                        f"{affectation.chambre.numero}. "
                        "Votre affectation est actuellement prévue."
                    ),
                    type_notification=(
    Notification.TypeNotification.AFFECTATION
),
                    lien="/accounts/espace-etudiant/",
                )

                messages.success(
                    request,
                    (
                        "L’étudiant a été affecté à la chambre "
                        "avec succès. La place est maintenant "
                        "réservée."
                    ),
                )

                return redirect(
                    "hebergement:"
                    "liste_affectations_responsable"
                )

        else:
            messages.error(
                request,
                (
                    "L’affectation n’a pas été enregistrée. "
                    "Corrigez les erreurs indiquées."
                ),
            )

    else:
        aujourd_hui = timezone.localdate()

        date_debut_annee = (
            demande.annee_universitaire.date_debut
        )

        date_fin_annee = (
            demande.annee_universitaire.date_fin
        )

        # La date initiale doit rester dans la période
        # de l’année universitaire.
        date_entree_initiale = max(
            aujourd_hui,
            date_debut_annee,
        )

        date_entree_initiale = min(
            date_entree_initiale,
            date_fin_annee,
        )

        formulaire = AffectationForm(
            initial={
                "date_entree_prevue": (
                    date_entree_initiale
                ),
                "date_sortie_prevue": (
                    date_fin_annee
                ),
            }
        )

    return render(
        request,
        (
            "hebergement/responsable/"
            "creer_affectation.html"
        ),
        {
            "formulaire": formulaire,
            "demande": demande,
        },
    )


# ============================================================
# RESPONSABLE — LISTE DES AFFECTATIONS
# ============================================================

@login_required
def liste_affectations_responsable(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    annee_selectionnee = request.GET.get(
        "annee",
        "",
    ).strip()

    batiment_selectionne = request.GET.get(
        "batiment",
        "",
    ).strip()

    chambre_selectionnee = request.GET.get(
        "chambre",
        "",
    ).strip()

    date_debut = request.GET.get(
        "date_debut",
        "",
    ).strip()

    date_fin = request.GET.get(
        "date_fin",
        "",
    ).strip()

    affectations = (
        Affectation.objects
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
            "demande_hebergement",
            "creee_par",
        )
        .order_by(
            "-date_creation",
        )
    )

    # ========================================================
    # RECHERCHE TEXTUELLE
    # ========================================================

    if recherche:
        affectations = affectations.filter(
            Q(
                etudiant__matricule__icontains=recherche
            )
            | Q(
                etudiant__cne__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__username__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__first_name__icontains=recherche
            )
            | Q(
                etudiant__utilisateur__last_name__icontains=recherche
            )
            | Q(
                chambre__numero__icontains=recherche
            )
            | Q(
                chambre__batiment__code__icontains=recherche
            )
            | Q(
                chambre__batiment__nom__icontains=recherche
            )
        ).distinct()

    # ========================================================
    # FILTRE PAR STATUT
    # ========================================================

    statuts_valides = {
        valeur
        for valeur, libelle
        in Affectation.Statut.choices
    }

    if (
        statut_selectionne
        and statut_selectionne in statuts_valides
    ):
        affectations = affectations.filter(
            statut=statut_selectionne,
        )

    # ========================================================
    # FILTRE PAR ANNÉE UNIVERSITAIRE
    # ========================================================

    if annee_selectionnee.isdigit():
        affectations = affectations.filter(
            annee_universitaire_id=int(
                annee_selectionnee
            ),
        )

    # ========================================================
    # FILTRE PAR BÂTIMENT
    # ========================================================

    if batiment_selectionne.isdigit():
        affectations = affectations.filter(
            chambre__batiment_id=int(
                batiment_selectionne
            ),
        )

    # ========================================================
    # FILTRE PAR CHAMBRE
    # ========================================================

    if chambre_selectionnee.isdigit():
        affectations = affectations.filter(
            chambre_id=int(
                chambre_selectionnee
            ),
        )

    # ========================================================
    # FILTRE PAR DATE D'ENTRÉE PRÉVUE
    # ========================================================

    if date_debut:
        affectations = affectations.filter(
            date_entree_prevue__gte=date_debut,
        )

    if date_fin:
        affectations = affectations.filter(
            date_entree_prevue__lte=date_fin,
        )

    # ========================================================
    # LISTES DES FILTRES
    # ========================================================

    annees_universitaires = (
        AnneeUniversitaire.objects
        .all()
        .order_by("-date_debut")
    )

    batiments = (
        Batiment.objects
        .all()
        .order_by("code")
    )

    chambres = (
        Chambre.objects
        .select_related("batiment")
        .order_by(
            "batiment__code",
            "etage",
            "numero",
        )
    )

    if batiment_selectionne.isdigit():
        chambres = chambres.filter(
            batiment_id=int(
                batiment_selectionne
            ),
        )

    # ========================================================
    # STATISTIQUES GLOBALES
    # ========================================================

    affectations_globales = Affectation.objects.all()

    nombre_total_global = (
        affectations_globales.count()
    )

    nombre_prevues = (
        affectations_globales
        .filter(
            statut=Affectation.Statut.PREVUE,
        )
        .count()
    )

    nombre_actives = (
        affectations_globales
        .filter(
            statut=Affectation.Statut.ACTIVE,
        )
        .count()
    )

    nombre_cloturees = (
        affectations_globales
        .filter(
            statut=Affectation.Statut.CLOTUREE,
        )
        .count()
    )

    nombre_annulees = (
        affectations_globales
        .filter(
            statut=Affectation.Statut.ANNULEE,
        )
        .count()
    )

    nombre_entrees_confirmees = (
        affectations_globales
        .exclude(
            date_entree_reelle__isnull=True,
        )
        .count()
    )

    nombre_sorties_confirmees = (
        affectations_globales
        .exclude(
            date_sortie_reelle__isnull=True,
        )
        .count()
    )

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        affectations,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    parametres_filtres = request.GET.copy()

    if "page" in parametres_filtres:
        parametres_filtres.pop("page")

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "affectations": page_obj,
        "page_obj": page_obj,

        "recherche": recherche,
        "statut_selectionne": statut_selectionne,
        "annee_selectionnee": annee_selectionnee,
        "batiment_selectionne": batiment_selectionne,
        "chambre_selectionnee": chambre_selectionnee,
        "date_debut": date_debut,
        "date_fin": date_fin,

        "choix_statuts": Affectation.Statut.choices,
        "annees_universitaires": annees_universitaires,
        "batiments": batiments,
        "chambres": chambres,

        "nombre_affectations": paginator.count,
        "nombre_total_global": nombre_total_global,
        "nombre_prevues": nombre_prevues,
        "nombre_actives": nombre_actives,
        "nombre_cloturees": nombre_cloturees,
        "nombre_annulees": nombre_annulees,
        "nombre_entrees_confirmees": (
            nombre_entrees_confirmees
        ),
        "nombre_sorties_confirmees": (
            nombre_sorties_confirmees
        ),

        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        "hebergement/responsable/affectations.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — CONFIRMER L'ENTRÉE
# ============================================================

@login_required
@transaction.atomic
def confirmer_entree_affectation(request, affectation_id):
    utilisateur = verifier_responsable(request)

    affectation = get_object_or_404(
        Affectation.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
        ),
        pk=affectation_id,
    )

    if request.method != "POST":
        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    if affectation.statut != Affectation.Statut.PREVUE:
        messages.error(
            request,
            "Seule une affectation prévue peut être activée.",
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    date_entree_saisie = request.POST.get(
        "date_entree_reelle",
        "",
    ).strip()

    if date_entree_saisie:
        try:
            date_entree_reelle = datetime.strptime(
                date_entree_saisie,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            messages.error(
                request,
                "La date d'entrée saisie est invalide.",
            )

            return redirect(
                "hebergement:liste_affectations_responsable"
            )

    else:
        date_entree_reelle = timezone.localdate()

    if date_entree_reelle < affectation.date_entree_prevue:
        messages.error(
            request,
            (
                "La date d'entrée réelle ne peut pas être "
                "antérieure à la date d'entrée prévue."
            ),
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    affectation.confirmer_entree(
        date_entree=date_entree_reelle
    )

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=HistoriqueAction.TypeAction.VALIDATION,
        entite="Affectation",
        identifiant_entite=affectation.pk,
        description=(
            "Confirmation de l'entrée de l'étudiant "
            f"{affectation.etudiant.matricule} dans la chambre "
            f"{affectation.chambre.numero}."
        ),
        request=request,
        anciennes_valeurs={
            "statut": Affectation.Statut.PREVUE,
            "date_entree_reelle": None,
        },
        nouvelles_valeurs={
            "statut": affectation.statut,
            "date_entree_reelle": str(
                affectation.date_entree_reelle
            ),
        },
    )

    creer_notification(
    utilisateur=affectation.etudiant.utilisateur,
    titre="Entrée confirmée",
    message=(
        "Votre entrée dans la chambre "
        f"{affectation.chambre.batiment.code}/"
        f"{affectation.chambre.numero} a été confirmée."
    ),
    type_notification=(
    Notification.TypeNotification.AFFECTATION
),
    lien="/accounts/espace-etudiant/",
)

    messages.success(
        request,
        (
            "L'entrée de l'étudiant dans la chambre "
            "a été confirmée avec succès."
        ),
    )

    return redirect(
        "hebergement:liste_affectations_responsable"
    )

# ============================================================
# RESPONSABLE — ANNULER UNE AFFECTATION PRÉVUE
# ============================================================

@login_required
@transaction.atomic
def annuler_affectation(request, affectation_id):
    utilisateur = verifier_responsable(request)

    affectation = get_object_or_404(
        Affectation.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
            "demande_hebergement",
        ),
        pk=affectation_id,
    )

    if request.method != "POST":
        messages.error(
            request,
            "Cette action doit être effectuée depuis le formulaire.",
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    if affectation.statut != Affectation.Statut.PREVUE:
        messages.error(
            request,
            (
                "Seule une affectation prévue "
                "peut être annulée."
            ),
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    motif_annulation = request.POST.get(
        "motif_annulation",
        "",
    ).strip()

    if not motif_annulation:
        messages.error(
            request,
            "Le motif d’annulation est obligatoire.",
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    # Verrouillage de la chambre afin de sécuriser
    # la libération de la place réservée.
    chambre = get_object_or_404(
        Chambre.objects
        .select_for_update()
        .select_related(
            "batiment",
        ),
        pk=affectation.chambre_id,
    )

    ancien_statut = affectation.statut

    try:
        affectation.annuler()

    except ValidationError as erreur:
        message_erreur = (
            " ".join(erreur.messages)
            if hasattr(erreur, "messages")
            else str(erreur)
        )

        messages.error(
            request,
            message_erreur,
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    # Mise à jour de l’état de la chambre après libération.
    chambre.mettre_a_jour_etat_occupation()

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="Affectation",
        identifiant_entite=affectation.pk,
        description=(
            "Annulation de l’affectation prévue de "
            f"l’étudiant {affectation.etudiant.matricule} "
            "dans la chambre "
            f"{affectation.chambre.batiment.code}/"
            f"{affectation.chambre.numero}. "
            f"Motif : {motif_annulation}"
        ),
        request=request,
        anciennes_valeurs={
            "statut": ancien_statut,
        },
        nouvelles_valeurs={
            "statut": affectation.statut,
            "motif_annulation": motif_annulation,
        },
    )

    creer_notification(
        utilisateur=affectation.etudiant.utilisateur,
        titre="Affectation annulée",
        message=(
            "Votre affectation prévue dans la chambre "
            f"{affectation.chambre.batiment.code}/"
            f"{affectation.chambre.numero} a été annulée. "
            f"Motif : {motif_annulation}"
        ),
        type_notification=(
    Notification.TypeNotification.AFFECTATION
),
        lien="/accounts/espace-etudiant/",
    )

    messages.success(
        request,
        (
            "L’affectation prévue a été annulée. "
            "La place réservée est maintenant libérée."
        ),
    )

    return redirect(
        "hebergement:liste_affectations_responsable"
    )

# ============================================================
# RESPONSABLE — CLÔTURER UNE AFFECTATION
# ============================================================

@login_required
@transaction.atomic
def cloturer_affectation(request, affectation_id):
    utilisateur = verifier_responsable(request)

    affectation = get_object_or_404(
        Affectation.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
        ),
        pk=affectation_id,
    )

    if affectation.statut != Affectation.Statut.ACTIVE:
        messages.error(
            request,
            "Seule une affectation active peut être clôturée.",
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    # ========================================================
    # AFFICHAGE DU FORMULAIRE
    # ========================================================

    if request.method == "GET":
        return render(
            request,
            "hebergement/responsable/cloturer_affectation.html",
            {
                "affectation": affectation,
            },
        )

    # ========================================================
    # TRAITEMENT
    # ========================================================

    date_sortie_saisie = request.POST.get(
        "date_sortie_reelle",
        "",
    ).strip()

    motif_sortie = request.POST.get(
        "motif_sortie",
        "",
    ).strip()

    if not motif_sortie:
        messages.error(
            request,
            "Le motif de sortie est obligatoire.",
        )

        return render(
            request,
            "hebergement/responsable/cloturer_affectation.html",
            {
                "affectation": affectation,
            },
        )

    if not date_sortie_saisie:
        messages.error(
            request,
            "La date de sortie est obligatoire.",
        )

        return render(
            request,
            "hebergement/responsable/cloturer_affectation.html",
            {
                "affectation": affectation,
            },
        )

    try:
        date_sortie_reelle = datetime.strptime(
            date_sortie_saisie,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        messages.error(
            request,
            "La date de sortie saisie est invalide.",
        )

        return render(
            request,
            "hebergement/responsable/cloturer_affectation.html",
            {
                "affectation": affectation,
            },
        )

    if (
        affectation.date_entree_reelle
        and date_sortie_reelle
        < affectation.date_entree_reelle
    ):
        messages.error(
            request,
            (
                "La date de sortie ne peut pas être "
                "antérieure à la date d'entrée réelle."
            ),
        )

        return render(
            request,
            "hebergement/responsable/cloturer_affectation.html",
            {
                "affectation": affectation,
            },
        )

    if (
        affectation.date_sortie_prevue
        and date_sortie_reelle
        > affectation.date_sortie_prevue
    ):
        messages.error(
            request,
            (
                "La date de sortie ne peut pas être "
                "postérieure à la date de sortie prévue."
            ),
        )

        return render(
            request,
            "hebergement/responsable/cloturer_affectation.html",
            {
                "affectation": affectation,
            },
        )

    ancien_statut = affectation.statut

    affectation.cloturer(
        motif_sortie=motif_sortie,
        date_sortie=date_sortie_reelle,
    )

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=HistoriqueAction.TypeAction.CLOTURE,
        entite="Affectation",
        identifiant_entite=affectation.pk,
        description=(
            "Clôture de l'affectation de l'étudiant "
            f"{affectation.etudiant.matricule}, chambre "
            f"{affectation.chambre.batiment.code}/"
            f"{affectation.chambre.numero}."
        ),
        request=request,
        anciennes_valeurs={
            "statut": ancien_statut,
        },
        nouvelles_valeurs={
            "statut": affectation.statut,
            "date_sortie_reelle": str(
                affectation.date_sortie_reelle
            ),
            "motif_sortie": affectation.motif_sortie,
        },
    )

    creer_notification(
        utilisateur=affectation.etudiant.utilisateur,
        titre="Fin de votre affectation",
        message=(
            "Votre affectation à la chambre "
            f"{affectation.chambre.batiment.code}/"
            f"{affectation.chambre.numero} "
            f"a été clôturée le "
            f"{affectation.date_sortie_reelle.strftime('%d/%m/%Y')}."
        ),
        type_notification="AFFECTATION",
        lien="/accounts/espace-etudiant/",
    )

    messages.success(
        request,
        (
            "L'affectation a été clôturée avec succès. "
            "La place dans la chambre est désormais disponible."
        ),
    )

    return redirect(
        "hebergement:liste_affectations_responsable"
    )


# ============================================================
# RESPONSABLE — TRANSFÉRER UN ÉTUDIANT
# ============================================================

@login_required
@transaction.atomic
def transferer_affectation(request, affectation_id):
    utilisateur = verifier_responsable(request)

    affectation = get_object_or_404(
        Affectation.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "etudiant__utilisateur",
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
            "demande_hebergement",
        ),
        pk=affectation_id,
    )

    if affectation.statut != Affectation.Statut.ACTIVE:
        messages.error(
            request,
            (
                "Seule une affectation active peut faire "
                "l’objet d’un transfert."
            ),
        )

        return redirect(
            "hebergement:liste_affectations_responsable"
        )

    ancienne_chambre = affectation.chambre

    if request.method == "POST":
        formulaire = TransfertEtudiantForm(
            request.POST,
            affectation=affectation,
        )

        if formulaire.is_valid():
            nouvelle_chambre_selectionnee = (
                formulaire.cleaned_data["nouvelle_chambre"]
            )

            motif = formulaire.cleaned_data["motif"]

            date_transfert = (
                formulaire.cleaned_data["date_transfert"]
            )

            # Verrouillage de la nouvelle chambre pour empêcher
            # deux transferts simultanés sur la dernière place.
            nouvelle_chambre = get_object_or_404(
                Chambre.objects
                .select_for_update()
                .select_related(
                    "batiment",
                ),
                pk=nouvelle_chambre_selectionnee.pk,
            )

            try:
                resultat_transfert = transferer_etudiant(
                    affectation_active=affectation,
                    nouvelle_chambre=nouvelle_chambre,
                    motif=motif,
                    utilisateur=utilisateur,
                    date_transfert=date_transfert,
                )

            except ValidationError as erreur:
                if hasattr(erreur, "message_dict"):
                    for champ, erreurs in (
                        erreur.message_dict.items()
                    ):
                        champ_formulaire = (
                            champ
                            if champ in formulaire.fields
                            else None
                        )

                        for message in erreurs:
                            formulaire.add_error(
                                champ_formulaire,
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
                        HistoriqueAction
                        .TypeAction
                        .TRANSFERT
                    ),
                    entite="Transfert",
                    identifiant_entite=(
                        resultat_transfert.pk
                    ),
                    description=(
                        "Transfert de l’étudiant "
                        f"{affectation.etudiant.matricule} "
                        "de la chambre "
                        f"{ancienne_chambre.batiment.code}/"
                        f"{ancienne_chambre.numero} vers "
                        f"{nouvelle_chambre.batiment.code}/"
                        f"{nouvelle_chambre.numero}."
                    ),
                    request=request,
                    anciennes_valeurs={
                        "batiment": (
                            ancienne_chambre.batiment.code
                        ),
                        "chambre": (
                            ancienne_chambre.numero
                        ),
                        "affectation": (
                            resultat_transfert
                            .ancienne_affectation_id
                        ),
                    },
                    nouvelles_valeurs={
                        "batiment": (
                            nouvelle_chambre.batiment.code
                        ),
                        "chambre": (
                            nouvelle_chambre.numero
                        ),
                        "affectation": (
                            resultat_transfert
                            .nouvelle_affectation_id
                        ),
                        "date_transfert": str(
                            resultat_transfert.date_transfert
                        ),
                        "motif": (
                            resultat_transfert.motif
                        ),
                    },
                )

                creer_notification(
                    utilisateur=(
                        affectation.etudiant.utilisateur
                    ),
                    titre="Transfert de chambre",
                    message=(
                        "Vous avez été transféré de la chambre "
                        f"{ancienne_chambre.batiment.code}/"
                        f"{ancienne_chambre.numero} vers "
                        f"{nouvelle_chambre.batiment.code}/"
                        f"{nouvelle_chambre.numero}. "
                        f"Motif : {motif}"
                    ),
                    type_notification=(
    Notification.TypeNotification.AFFECTATION
),
                    lien="/accounts/espace-etudiant/",
                )

                messages.success(
                    request,
                    (
                        "L’étudiant a été transféré vers la "
                        "nouvelle chambre avec succès."
                    ),
                )

                return redirect(
                    "hebergement:"
                    "liste_affectations_responsable"
                )

        else:
            messages.error(
                request,
                (
                    "Le transfert n’a pas été effectué. "
                    "Corrigez les erreurs indiquées."
                ),
            )

    else:
        formulaire = TransfertEtudiantForm(
            affectation=affectation,
            initial={
                "date_transfert": timezone.localdate(),
            },
        )

    return render(
        request,
        (
            "hebergement/responsable/"
            "transferer_affectation.html"
        ),
        {
            "affectation": affectation,
            "formulaire": formulaire,
        },
    )


# ============================================================
# RESPONSABLE — HISTORIQUE DES TRANSFERTS
# ============================================================

@login_required
def liste_transferts_responsable(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    annee_selectionnee = request.GET.get(
        "annee",
        "",
    ).strip()

    ancien_batiment_selectionne = request.GET.get(
        "ancien_batiment",
        "",
    ).strip()

    nouveau_batiment_selectionne = request.GET.get(
        "nouveau_batiment",
        "",
    ).strip()

    date_debut = request.GET.get(
        "date_debut",
        "",
    ).strip()

    date_fin = request.GET.get(
        "date_fin",
        "",
    ).strip()

    transferts = (
        Transfert.objects
        .select_related(
            "ancienne_affectation",
            "ancienne_affectation__etudiant",
            "ancienne_affectation__etudiant__utilisateur",
            "ancienne_affectation__chambre",
            "ancienne_affectation__chambre__batiment",
            "ancienne_affectation__annee_universitaire",
            "nouvelle_affectation",
            "nouvelle_affectation__etudiant",
            "nouvelle_affectation__etudiant__utilisateur",
            "nouvelle_affectation__chambre",
            "nouvelle_affectation__chambre__batiment",
            "nouvelle_affectation__annee_universitaire",
            "effectue_par",
        )
        .order_by(
            "-date_transfert",
            "-date_creation",
        )
    )

    # ========================================================
    # RECHERCHE
    # ========================================================

    if recherche:
        transferts = transferts.filter(
            Q(
                ancienne_affectation__etudiant__matricule__icontains=(
                    recherche
                )
            )
            | Q(
                ancienne_affectation__etudiant__cne__icontains=(
                    recherche
                )
            )
            | Q(
                ancienne_affectation__etudiant__utilisateur__username__icontains=(
                    recherche
                )
            )
            | Q(
                ancienne_affectation__etudiant__utilisateur__first_name__icontains=(
                    recherche
                )
            )
            | Q(
                ancienne_affectation__etudiant__utilisateur__last_name__icontains=(
                    recherche
                )
            )
            | Q(
                ancienne_affectation__chambre__numero__icontains=(
                    recherche
                )
            )
            | Q(
                ancienne_affectation__chambre__batiment__code__icontains=(
                    recherche
                )
            )
            | Q(
                nouvelle_affectation__chambre__numero__icontains=(
                    recherche
                )
            )
            | Q(
                nouvelle_affectation__chambre__batiment__code__icontains=(
                    recherche
                )
            )
            | Q(
                motif__icontains=recherche
            )
        ).distinct()

    # ========================================================
    # FILTRE PAR ANNÉE UNIVERSITAIRE
    # ========================================================

    if annee_selectionnee.isdigit():
        transferts = transferts.filter(
            nouvelle_affectation__annee_universitaire_id=int(
                annee_selectionnee
            )
        )

    # ========================================================
    # FILTRE PAR ANCIEN BÂTIMENT
    # ========================================================

    if ancien_batiment_selectionne.isdigit():
        transferts = transferts.filter(
            ancienne_affectation__chambre__batiment_id=int(
                ancien_batiment_selectionne
            )
        )

    # ========================================================
    # FILTRE PAR NOUVEAU BÂTIMENT
    # ========================================================

    if nouveau_batiment_selectionne.isdigit():
        transferts = transferts.filter(
            nouvelle_affectation__chambre__batiment_id=int(
                nouveau_batiment_selectionne
            )
        )

    # ========================================================
    # FILTRE PAR DATE
    # ========================================================

    date_debut_valide = None
    date_fin_valide = None

    if date_debut:
        try:
            date_debut_valide = datetime.strptime(
                date_debut,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            messages.error(
                request,
                "La date de début du filtre est invalide.",
            )

    if date_fin:
        try:
            date_fin_valide = datetime.strptime(
                date_fin,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            messages.error(
                request,
                "La date de fin du filtre est invalide.",
            )

    if (
        date_debut_valide
        and date_fin_valide
        and date_fin_valide < date_debut_valide
    ):
        messages.error(
            request,
            (
                "La date de fin du filtre ne peut pas être "
                "antérieure à la date de début."
            ),
        )

    else:
        if date_debut_valide:
            transferts = transferts.filter(
                date_transfert__gte=date_debut_valide
            )

        if date_fin_valide:
            transferts = transferts.filter(
                date_transfert__lte=date_fin_valide
            )

    # ========================================================
    # DONNÉES DES FILTRES
    # ========================================================

    annees_universitaires = (
        AnneeUniversitaire.objects
        .all()
        .order_by(
            "-date_debut",
        )
    )

    batiments = (
        Batiment.objects
        .all()
        .order_by(
            "code",
        )
    )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    transferts_globaux = (
        Transfert.objects
        .select_related(
            "ancienne_affectation__chambre__batiment",
            "nouvelle_affectation__chambre__batiment",
            "nouvelle_affectation__annee_universitaire",
        )
        .all()
    )

    nombre_total_global = (
        transferts_globaux.count()
    )

    annee_active = (
        AnneeUniversitaire.objects
        .filter(
            statut=AnneeUniversitaire.Statut.ACTIVE,
        )
        .first()
    )

    nombre_transferts_annee_active = 0

    if annee_active:
        nombre_transferts_annee_active = (
            transferts_globaux
            .filter(
                nouvelle_affectation__annee_universitaire=(
                    annee_active
                )
            )
            .count()
        )

    nombre_transferts_meme_batiment = 0
    nombre_transferts_autre_batiment = 0

    for transfert in transferts_globaux:
        ancien_batiment_id = (
            transfert
            .ancienne_affectation
            .chambre
            .batiment_id
        )

        nouveau_batiment_id = (
            transfert
            .nouvelle_affectation
            .chambre
            .batiment_id
        )

        if (
            ancien_batiment_id
            == nouveau_batiment_id
        ):
            nombre_transferts_meme_batiment += 1

        else:
            nombre_transferts_autre_batiment += 1

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        transferts,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    parametres_filtres = request.GET.copy()

    parametres_filtres.pop(
        "page",
        None,
    )

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "transferts": page_obj,
        "page_obj": page_obj,

        "recherche": recherche,
        "annee_selectionnee": annee_selectionnee,
        "ancien_batiment_selectionne": (
            ancien_batiment_selectionne
        ),
        "nouveau_batiment_selectionne": (
            nouveau_batiment_selectionne
        ),
        "date_debut": date_debut,
        "date_fin": date_fin,

        "annees_universitaires": (
            annees_universitaires
        ),
        "batiments": batiments,

        "nombre_transferts": paginator.count,
        "nombre_total_global": (
            nombre_total_global
        ),
        "nombre_transferts_annee_active": (
            nombre_transferts_annee_active
        ),
        "nombre_transferts_meme_batiment": (
            nombre_transferts_meme_batiment
        ),
        "nombre_transferts_autre_batiment": (
            nombre_transferts_autre_batiment
        ),

        "annee_active": annee_active,
        "chaine_filtres": chaine_filtres,
    }

    return render(
    request,
    "hebergement/responsable/transferts.html",
    contexte,
)
# ============================================================
# RESPONSABLE — LISTE DES BÂTIMENTS
# ============================================================

@login_required
def liste_batiments(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    occupation_selectionnee = request.GET.get(
        "occupation",
        "",
    ).strip()

    nombre_etages_selectionne = request.GET.get(
        "nombre_etages",
        "",
    ).strip()

    batiments_queryset = (
        Batiment.objects
        .prefetch_related(
            "chambres",
            "chambres__affectations",
        )
        .order_by("code")
    )

    # ========================================================
    # RECHERCHE
    # ========================================================

    if recherche:
        batiments_queryset = batiments_queryset.filter(
            Q(code__icontains=recherche)
            | Q(nom__icontains=recherche)
            | Q(description__icontains=recherche)
        ).distinct()

    # ========================================================
    # FILTRE PAR STATUT
    # ========================================================

    statuts_valides = {
        valeur
        for valeur, libelle
        in Batiment.Statut.choices
    }

    if (
        statut_selectionne
        and statut_selectionne in statuts_valides
    ):
        batiments_queryset = batiments_queryset.filter(
            statut=statut_selectionne,
        )

    # ========================================================
    # FILTRE PAR NOMBRE D'ÉTAGES
    # ========================================================

    if nombre_etages_selectionne.isdigit():
        batiments_queryset = batiments_queryset.filter(
            nombre_etages=int(
                nombre_etages_selectionne
            ),
        )

    # ========================================================
    # CALCUL DES DONNÉES PAR BÂTIMENT
    # ========================================================

    batiments = list(batiments_queryset)

    for batiment in batiments:
        chambres = list(
            batiment.chambres.all()
        )

        batiment.nombre_chambres_calcule = len(
            chambres
        )

        batiment.nombre_chambres_actives_calcule = sum(
            1
            for chambre in chambres
            if chambre.est_active
        )

        batiment.nombre_chambres_inactives_calcule = sum(
            1
            for chambre in chambres
            if not chambre.est_active
        )

        batiment.nombre_chambres_disponibles_calcule = sum(
            1
            for chambre in chambres
            if (
                chambre.est_active
                and chambre.etat
                in {
                    Chambre.Etat.DISPONIBLE,
                    Chambre.Etat.PARTIELLE,
                }
                and chambre.nombre_places_disponibles > 0
            )
        )

        batiment.nombre_chambres_completes_calcule = sum(
            1
            for chambre in chambres
            if chambre.etat == Chambre.Etat.COMPLETE
        )

        batiment.nombre_chambres_maintenance_calcule = sum(
            1
            for chambre in chambres
            if chambre.etat
            in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
            }
        )

        batiment.capacite_totale_calculee = (
            batiment.capacite_totale
        )

        batiment.places_occupees_calculees = (
            batiment.nombre_places_occupees
        )

        batiment.places_disponibles_calculees = (
            batiment.nombre_places_disponibles
        )

        batiment.taux_occupation_calcule = (
            batiment.taux_occupation
        )

    # ========================================================
    # FILTRE PAR OCCUPATION
    # ========================================================

    if occupation_selectionnee == "VIDE":
        batiments = [
            batiment
            for batiment in batiments
            if batiment.places_occupees_calculees == 0
        ]

    elif occupation_selectionnee == "PARTIEL":
        batiments = [
            batiment
            for batiment in batiments
            if (
                batiment.places_occupees_calculees > 0
                and batiment.places_disponibles_calculees > 0
            )
        ]

    elif occupation_selectionnee == "COMPLET":
        batiments = [
            batiment
            for batiment in batiments
            if (
                batiment.capacite_totale_calculee > 0
                and batiment.places_disponibles_calculees == 0
            )
        ]

    # ========================================================
    # LISTE DES NOMBRES D'ÉTAGES
    # ========================================================

    nombres_etages = (
        Batiment.objects
        .values_list(
            "nombre_etages",
            flat=True,
        )
        .distinct()
        .order_by("nombre_etages")
    )

    # ========================================================
    # STATISTIQUES GLOBALES
    # ========================================================

    tous_les_batiments = list(
        Batiment.objects
        .prefetch_related(
            "chambres",
            "chambres__affectations",
        )
    )

    nombre_total_global = len(
        tous_les_batiments
    )

    nombre_batiments_actifs = sum(
        1
        for batiment in tous_les_batiments
        if batiment.statut == Batiment.Statut.ACTIF
    )

    nombre_batiments_inactifs = sum(
        1
        for batiment in tous_les_batiments
        if batiment.statut == Batiment.Statut.INACTIF
    )

    nombre_batiments_maintenance = sum(
        1
        for batiment in tous_les_batiments
        if batiment.statut
        == Batiment.Statut.MAINTENANCE
    )

    nombre_chambres_global = sum(
    len(batiment.chambres.all())
    for batiment in tous_les_batiments
    )

    capacite_totale_globale = sum(
        batiment.capacite_totale
        for batiment in tous_les_batiments
    )

    places_occupees_globales = sum(
        batiment.nombre_places_occupees
        for batiment in tous_les_batiments
    )

    places_disponibles_globales = sum(
        batiment.nombre_places_disponibles
        for batiment in tous_les_batiments
    )

    taux_occupation_global = (
        round(
            (
                places_occupees_globales
                / capacite_totale_globale
            )
            * 100,
            2,
        )
        if capacite_totale_globale > 0
        else 0
    )

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        batiments,
        12,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    parametres_filtres = request.GET.copy()

    if "page" in parametres_filtres:
        parametres_filtres.pop("page")

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "batiments": page_obj,
        "page_obj": page_obj,

        "recherche": recherche,
        "statut_selectionne": statut_selectionne,
        "occupation_selectionnee": (
            occupation_selectionnee
        ),
        "nombre_etages_selectionne": (
            nombre_etages_selectionne
        ),

        "choix_statuts": Batiment.Statut.choices,
        "nombres_etages": nombres_etages,

        "nombre_batiments": paginator.count,
        "nombre_total_global": nombre_total_global,
        "nombre_batiments_actifs": (
            nombre_batiments_actifs
        ),
        "nombre_batiments_inactifs": (
            nombre_batiments_inactifs
        ),
        "nombre_batiments_maintenance": (
            nombre_batiments_maintenance
        ),
        "nombre_chambres_global": (
            nombre_chambres_global
        ),
        "capacite_totale_globale": (
            capacite_totale_globale
        ),
        "places_occupees_globales": (
            places_occupees_globales
        ),
        "places_disponibles_globales": (
            places_disponibles_globales
        ),
        "taux_occupation_global": (
            taux_occupation_global
        ),

        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        "hebergement/responsable/batiments/liste.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — CRÉER UN BÂTIMENT
# ============================================================

@login_required
@transaction.atomic
def creer_batiment(request):
    utilisateur = verifier_responsable(request)

    if request.method == "POST":
        formulaire = BatimentForm(
            request.POST
        )

        if formulaire.is_valid():
            batiment = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur,
                type_action=(
                    HistoriqueAction.TypeAction.CREATION
                ),
                entite="Batiment",
                identifiant_entite=batiment.pk,
                description=(
                    f"Création du bâtiment "
                    f"{batiment.code} — {batiment.nom}."
                ),
                request=request,
                nouvelles_valeurs={
                    "code": batiment.code,
                    "nom": batiment.nom,
                    "nombre_etages": (
                        batiment.nombre_etages
                    ),
                    "statut": batiment.statut,
                },
            )

            messages.success(
                request,
                "Le bâtiment a été créé avec succès.",
            )

            return redirect(
                "hebergement:liste_batiments"
            )

    else:
        formulaire = BatimentForm()

    return render(
        request,
        "hebergement/responsable/batiments/formulaire.html",
        {
            "formulaire": formulaire,
            "titre_page": "Ajouter un bâtiment",
            "bouton_validation": "Créer le bâtiment",
        },
    )


# ============================================================
# RESPONSABLE — MODIFIER UN BÂTIMENT
# ============================================================

@login_required
@transaction.atomic
def modifier_batiment(request, batiment_id):
    utilisateur = verifier_responsable(request)

    batiment = get_object_or_404(
        Batiment.objects.select_for_update(),
        pk=batiment_id,
    )

    valeurs_avant_modification = {
        "code": batiment.code,
        "nom": batiment.nom,
        "nombre_etages": batiment.nombre_etages,
        "statut": batiment.statut,
    }

    if request.method == "POST":
        formulaire = BatimentForm(
            request.POST,
            instance=batiment,
        )

        if formulaire.is_valid():
            batiment = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur,
                type_action=(
                    HistoriqueAction.TypeAction.MODIFICATION
                ),
                entite="Batiment",
                identifiant_entite=batiment.pk,
                description=(
                    f"Modification du bâtiment "
                    f"{batiment.code} — {batiment.nom}."
                ),
                request=request,
                anciennes_valeurs=(
                    valeurs_avant_modification
                ),
                nouvelles_valeurs={
                    "code": batiment.code,
                    "nom": batiment.nom,
                    "nombre_etages": (
                        batiment.nombre_etages
                    ),
                    "statut": batiment.statut,
                },
            )

            messages.success(
                request,
                "Le bâtiment a été modifié avec succès.",
            )

            return redirect(
    "hebergement:detail_batiment",
    batiment_id=batiment.pk,
)

    else:
        formulaire = BatimentForm(
            instance=batiment
        )

    return render(
        request,
        "hebergement/responsable/batiments/formulaire.html",
        {
            "formulaire": formulaire,
            "batiment": batiment,
            "titre_page": "Modifier un bâtiment",
            "bouton_validation": "Enregistrer",
        },
    )


# ============================================================
# RESPONSABLE — DÉTAIL D'UN BÂTIMENT
# ============================================================

@login_required
def detail_batiment(request, batiment_id):
    verifier_responsable(request)

    batiment = get_object_or_404(
        Batiment.objects.prefetch_related(
            "chambres",
            "chambres__affectations",
            "chambres__affectations__etudiant",
            "chambres__affectations__etudiant__utilisateur",
        ),
        pk=batiment_id,
    )

    chambres_queryset = (
        Chambre.objects
        .filter(
            batiment=batiment,
        )
        .prefetch_related(
            "affectations",
            "affectations__etudiant",
            "affectations__etudiant__utilisateur",
        )
        .order_by(
            "etage",
            "numero",
        )
    )

    chambres = list(
        chambres_queryset
    )

    # ========================================================
    # CALCUL DES DONNÉES PAR CHAMBRE
    # ========================================================

    for chambre in chambres:
        affectations_actives = [
            affectation
            for affectation in chambre.affectations.all()
            if affectation.statut == Affectation.Statut.ACTIVE
        ]

        chambre.affectations_actives_calculees = (
            affectations_actives
        )

        chambre.nombre_places_occupees_calcule = len(
            affectations_actives
        )

        chambre.nombre_places_disponibles_calculees = max(
            chambre.capacite
            - chambre.nombre_places_occupees_calcule,
            0,
        )

        chambre.taux_occupation_calcule = (
            round(
                (
                    chambre.nombre_places_occupees_calcule
                    / chambre.capacite
                )
                * 100,
                2,
            )
            if chambre.capacite > 0
            else 0
        )

    # ========================================================
    # STATISTIQUES DU BÂTIMENT
    # ========================================================

    nombre_chambres = len(
        chambres
    )

    nombre_chambres_actives = sum(
        1
        for chambre in chambres
        if chambre.est_active
    )

    nombre_chambres_inactives = sum(
        1
        for chambre in chambres
        if not chambre.est_active
    )

    nombre_chambres_disponibles = sum(
        1
        for chambre in chambres
        if (
            chambre.est_active
            and chambre.nombre_places_disponibles_calculees > 0
            and chambre.etat
            not in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
            }
        )
    )

    nombre_chambres_completes = sum(
        1
        for chambre in chambres
        if chambre.nombre_places_disponibles_calculees == 0
        and chambre.capacite > 0
    )

    nombre_chambres_maintenance = sum(
        1
        for chambre in chambres
        if chambre.etat == Chambre.Etat.MAINTENANCE
    )

    nombre_chambres_hors_service = sum(
        1
        for chambre in chambres
        if chambre.etat == Chambre.Etat.HORS_SERVICE
    )

    capacite_totale = sum(
        chambre.capacite
        for chambre in chambres
        if chambre.est_active
    )

    places_occupees = sum(
        chambre.nombre_places_occupees_calcule
        for chambre in chambres
        if chambre.est_active
    )

    places_disponibles = max(
        capacite_totale - places_occupees,
        0,
    )

    taux_occupation = (
        round(
            (
                places_occupees
                / capacite_totale
            )
            * 100,
            2,
        )
        if capacite_totale > 0
        else 0
    )

    # ========================================================
    # RÉPARTITION PAR ÉTAGE
    # ========================================================

    repartition_etages = []

    for etage in range(
        0,
        batiment.nombre_etages + 1,
    ):
        chambres_etage = [
            chambre
            for chambre in chambres
            if chambre.etage == etage
        ]

        if not chambres_etage:
            continue

        capacite_etage = sum(
            chambre.capacite
            for chambre in chambres_etage
            if chambre.est_active
        )

        occupation_etage = sum(
            chambre.nombre_places_occupees_calcule
            for chambre in chambres_etage
            if chambre.est_active
        )

        repartition_etages.append(
            {
                "numero": etage,
                "nombre_chambres": len(
                    chambres_etage
                ),
                "capacite": capacite_etage,
                "occupation": occupation_etage,
                "disponibilite": max(
                    capacite_etage - occupation_etage,
                    0,
                ),
                "taux_occupation": (
                    round(
                        (
                            occupation_etage
                            / capacite_etage
                        )
                        * 100,
                        2,
                    )
                    if capacite_etage > 0
                    else 0
                ),
            }
        )

    contexte = {
        "batiment": batiment,
        "chambres": chambres,

        "nombre_chambres": nombre_chambres,
        "nombre_chambres_actives": (
            nombre_chambres_actives
        ),
        "nombre_chambres_inactives": (
            nombre_chambres_inactives
        ),
        "nombre_chambres_disponibles": (
            nombre_chambres_disponibles
        ),
        "nombre_chambres_completes": (
            nombre_chambres_completes
        ),
        "nombre_chambres_maintenance": (
            nombre_chambres_maintenance
        ),
        "nombre_chambres_hors_service": (
            nombre_chambres_hors_service
        ),

        "capacite_totale": capacite_totale,
        "places_occupees": places_occupees,
        "places_disponibles": places_disponibles,
        "taux_occupation": taux_occupation,

        "repartition_etages": repartition_etages,
    }

    return render(
        request,
        "hebergement/responsable/batiments/detail.html",
        contexte,
    )
# ============================================================
# RESPONSABLE — LISTE DES CHAMBRES
# ============================================================

@login_required
def liste_chambres(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    batiment_selectionne = request.GET.get(
        "batiment",
        "",
    ).strip()

    etat_selectionne = request.GET.get(
        "etat",
        "",
    ).strip()

    type_selectionne = request.GET.get(
        "type_chambre",
        "",
    ).strip()

    etage_selectionne = request.GET.get(
        "etage",
        "",
    ).strip()

    activation_selectionnee = request.GET.get(
        "activation",
        "",
    ).strip()

    disponibilite_selectionnee = request.GET.get(
        "disponibilite",
        "",
    ).strip()

    chambres = (
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

    # ========================================================
    # RECHERCHE
    # ========================================================

    if recherche:
        chambres = chambres.filter(
            Q(
                numero__icontains=recherche
            )
            | Q(
                batiment__code__icontains=recherche
            )
            | Q(
                batiment__nom__icontains=recherche
            )
            | Q(
                description__icontains=recherche
            )
        ).distinct()

    # ========================================================
    # FILTRE PAR BÂTIMENT
    # ========================================================

    if batiment_selectionne.isdigit():
        chambres = chambres.filter(
            batiment_id=int(
                batiment_selectionne
            ),
        )

    # ========================================================
    # FILTRE PAR ÉTAT
    # ========================================================

    valeurs_etats = {
        valeur
        for valeur, libelle
        in Chambre.Etat.choices
    }

    if (
        etat_selectionne
        and etat_selectionne in valeurs_etats
    ):
        chambres = chambres.filter(
            etat=etat_selectionne,
        )

    # ========================================================
    # FILTRE PAR TYPE
    # ========================================================

    valeurs_types = {
        valeur
        for valeur, libelle
        in Chambre.TypeChambre.choices
    }

    if (
        type_selectionne
        and type_selectionne in valeurs_types
    ):
        chambres = chambres.filter(
            type_chambre=type_selectionne,
        )

    # ========================================================
    # FILTRE PAR ÉTAGE
    # ========================================================

    if etage_selectionne:
        try:
            numero_etage = int(
                etage_selectionne
            )

        except (TypeError, ValueError):
            numero_etage = None

        if numero_etage is not None:
            chambres = chambres.filter(
                etage=numero_etage,
            )

    # ========================================================
    # FILTRE PAR ACTIVATION
    # ========================================================

    if activation_selectionnee == "ACTIVE":
        chambres = chambres.filter(
            est_active=True,
        )

    elif activation_selectionnee == "INACTIVE":
        chambres = chambres.filter(
            est_active=False,
        )

    # ========================================================
    # CALCUL DES INFORMATIONS D’OCCUPATION
    # ========================================================

    liste_chambres = list(
        chambres
    )

    for chambre in liste_chambres:
        chambre.places_occupees_calculees = (
            chambre.nombre_places_occupees
        )

        chambre.places_disponibles_calculees = (
            chambre.nombre_places_disponibles
        )

        chambre.taux_occupation_calcule = (
            round(
                (
                    chambre.places_occupees_calculees
                    / chambre.capacite
                )
                * 100,
                1,
            )
            if chambre.capacite > 0
            else 0
        )

        chambre.est_disponible_calculee = (
            chambre.est_disponible_pour_affectation
            and chambre.places_disponibles_calculees > 0
        )

    # ========================================================
    # FILTRE PAR DISPONIBILITÉ
    # ========================================================

    if disponibilite_selectionnee == "DISPONIBLE":
        liste_chambres = [
            chambre
            for chambre in liste_chambres
            if chambre.est_disponible_calculee
        ]

    elif disponibilite_selectionnee == "COMPLETE":
        liste_chambres = [
            chambre
            for chambre in liste_chambres
            if (
                chambre.places_disponibles_calculees == 0
                and chambre.places_occupees_calculees > 0
            )
        ]

    elif disponibilite_selectionnee == "VIDE":
        liste_chambres = [
            chambre
            for chambre in liste_chambres
            if chambre.places_occupees_calculees == 0
        ]

    # ========================================================
    # VALEURS POUR LES FILTRES
    # ========================================================

    batiments = (
        Batiment.objects
        .all()
        .order_by(
            "code",
        )
    )

    etages = (
        Chambre.objects
        .values_list(
            "etage",
            flat=True,
        )
        .distinct()
        .order_by(
            "etage",
        )
    )

    # ========================================================
    # STATISTIQUES GLOBALES
    # ========================================================

    toutes_les_chambres = list(
        Chambre.objects
        .select_related(
            "batiment",
        )
        .prefetch_related(
            "affectations",
        )
    )

    nombre_total_global = len(
        toutes_les_chambres
    )

    nombre_chambres_actives = sum(
        1
        for chambre in toutes_les_chambres
        if chambre.est_active
    )

    nombre_chambres_inactives = sum(
        1
        for chambre in toutes_les_chambres
        if not chambre.est_active
    )

    nombre_chambres_disponibles = sum(
        1
        for chambre in toutes_les_chambres
        if (
            chambre.est_active
            and chambre.est_disponible_pour_affectation
            and chambre.nombre_places_disponibles > 0
        )
    )

    nombre_chambres_completes = sum(
        1
        for chambre in toutes_les_chambres
        if (
            chambre.est_active
            and chambre.nombre_places_disponibles == 0
            and chambre.nombre_places_occupees > 0
            and chambre.etat
            not in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
            }
        )
    )

    nombre_chambres_maintenance = sum(
        1
        for chambre in toutes_les_chambres
        if chambre.etat == Chambre.Etat.MAINTENANCE
    )

    capacite_totale = sum(
        chambre.capacite
        for chambre in toutes_les_chambres
        if chambre.est_active
    )

    places_occupees = sum(
        chambre.nombre_places_occupees
        for chambre in toutes_les_chambres
        if chambre.est_active
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

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        liste_chambres,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get(
            "page"
        ),
    )

    parametres_filtres = (
        request.GET.copy()
    )

    if "page" in parametres_filtres:
        parametres_filtres.pop(
            "page"
        )

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "chambres": page_obj,
        "page_obj": page_obj,

        "batiments": batiments,
        "etages": etages,

        "recherche": recherche,
        "batiment_selectionne": (
            batiment_selectionne
        ),
        "etat_selectionne": (
            etat_selectionne
        ),
        "type_selectionne": (
            type_selectionne
        ),
        "etage_selectionne": (
            etage_selectionne
        ),
        "activation_selectionnee": (
            activation_selectionnee
        ),
        "disponibilite_selectionnee": (
            disponibilite_selectionnee
        ),

        "choix_etats": (
            Chambre.Etat.choices
        ),
        "choix_types": (
            Chambre.TypeChambre.choices
        ),

        "nombre_chambres": (
            paginator.count
        ),
        "nombre_total_global": (
            nombre_total_global
        ),
        "nombre_chambres_actives": (
            nombre_chambres_actives
        ),
        "nombre_chambres_inactives": (
            nombre_chambres_inactives
        ),
        "nombre_chambres_disponibles": (
            nombre_chambres_disponibles
        ),
        "nombre_chambres_completes": (
            nombre_chambres_completes
        ),
        "nombre_chambres_maintenance": (
            nombre_chambres_maintenance
        ),

        "capacite_totale": (
            capacite_totale
        ),
        "places_occupees": (
            places_occupees
        ),
        "places_disponibles": (
            places_disponibles
        ),
        "taux_occupation": (
            taux_occupation
        ),

        "chaine_filtres": (
            chaine_filtres
        ),
    }

    return render(
        request,
        "hebergement/responsable/chambres/liste.html",
        contexte,
    )
    nombre_chambres_maintenance = sum(
        1
        for chambre in toutes_les_chambres
        if chambre.etat == Chambre.Etat.MAINTENANCE
    )

    capacite_totale = sum(
        chambre.capacite
        for chambre in toutes_les_chambres
        if chambre.est_active
    )

    places_occupees = sum(
        chambre.nombre_places_occupees
        for chambre in toutes_les_chambres
        if chambre.est_active
    )

    places_disponibles = max(
        capacite_totale - places_occupees,
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

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        liste_chambres,
        15,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    parametres_filtres = request.GET.copy()

    if "page" in parametres_filtres:
        parametres_filtres.pop("page")

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "chambres": page_obj,
        "page_obj": page_obj,

        "batiments": batiments,
        "etages": etages,

        "recherche": recherche,
        "batiment_selectionne": batiment_selectionne,
        "etat_selectionne": etat_selectionne,
        "type_selectionne": type_selectionne,
        "etage_selectionne": etage_selectionne,
        "activation_selectionnee": (
            activation_selectionnee
        ),
        "disponibilite_selectionnee": (
            disponibilite_selectionnee
        ),

        "choix_etats": Chambre.Etat.choices,
        "choix_types": Chambre.TypeChambre.choices,

        "nombre_chambres": paginator.count,
        "nombre_total_global": nombre_total_global,
        "nombre_chambres_actives": (
            nombre_chambres_actives
        ),
        "nombre_chambres_inactives": (
            nombre_chambres_inactives
        ),
        "nombre_chambres_disponibles": (
            nombre_chambres_disponibles
        ),
        "nombre_chambres_completes": (
            nombre_chambres_completes
        ),
        "nombre_chambres_maintenance": (
            nombre_chambres_maintenance
        ),

        "capacite_totale": capacite_totale,
        "places_occupees": places_occupees,
        "places_disponibles": places_disponibles,
        "taux_occupation": taux_occupation,

        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        "hebergement/responsable/chambres/liste.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — CRÉER UNE CHAMBRE
# ============================================================

@login_required
@transaction.atomic
def creer_chambre(request):
    utilisateur = verifier_responsable(request)

    batiment_initial = None
    batiment_id = request.GET.get(
        "batiment",
        "",
    ).strip()

    if batiment_id.isdigit():
        batiment_initial = (
            Batiment.objects
            .exclude(
                statut=Batiment.Statut.INACTIF,
            )
            .filter(
                pk=int(batiment_id),
            )
            .first()
        )

    if request.method == "POST":
        formulaire = ChambreForm(
            request.POST,
        )

        if formulaire.is_valid():
            chambre = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur,
                type_action=(
                    HistoriqueAction.TypeAction.CREATION
                ),
                entite="Chambre",
                identifiant_entite=chambre.pk,
                description=(
                    f"Création de la chambre "
                    f"{chambre.batiment.code}/"
                    f"{chambre.numero}."
                ),
                request=request,
                nouvelles_valeurs={
                    "batiment": chambre.batiment.code,
                    "numero": chambre.numero,
                    "etage": chambre.etage,
                    "capacite": chambre.capacite,
                    "type_chambre": chambre.type_chambre,
                    "etat": chambre.etat,
                    "est_active": chambre.est_active,
                },
            )

            messages.success(
                request,
                "La chambre a été créée avec succès.",
            )

            return redirect(
                "hebergement:liste_chambres"
            )

    else:
        formulaire = ChambreForm(
            initial={
                "batiment": batiment_initial,
                "etat": Chambre.Etat.DISPONIBLE,
                "est_active": True,
            }
        )

    return render(
        request,
        "hebergement/responsable/chambres/formulaire.html",
        {
            "formulaire": formulaire,
            "titre_page": "Ajouter une chambre",
            "bouton_validation": "Créer la chambre",
        },
    )


# ============================================================
# RESPONSABLE — MODIFIER UNE CHAMBRE
# ============================================================

@login_required
@transaction.atomic
def modifier_chambre(request, chambre_id):
    utilisateur = verifier_responsable(request)

    chambre = get_object_or_404(
        Chambre.objects
        .select_for_update()
        .select_related("batiment"),
        pk=chambre_id,
    )

    valeurs_avant_modification = {
        "batiment": chambre.batiment.code,
        "numero": chambre.numero,
        "etage": chambre.etage,
        "capacite": chambre.capacite,
        "type_chambre": chambre.type_chambre,
        "etat": chambre.etat,
        "est_active": chambre.est_active,
    }

    if request.method == "POST":
        formulaire = ChambreForm(
            request.POST,
            instance=chambre,
        )

        if formulaire.is_valid():
            chambre = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur,
                type_action=(
                    HistoriqueAction.TypeAction.MODIFICATION
                ),
                entite="Chambre",
                identifiant_entite=chambre.pk,
                description=(
                    f"Modification de la chambre "
                    f"{chambre.batiment.code}/"
                    f"{chambre.numero}."
                ),
                request=request,
                anciennes_valeurs=(
                    valeurs_avant_modification
                ),
                nouvelles_valeurs={
                    "batiment": (
                        chambre.batiment.code
                    ),
                    "numero": chambre.numero,
                    "etage": chambre.etage,
                    "capacite": chambre.capacite,
                    "type_chambre": (
                        chambre.type_chambre
                    ),
                    "etat": chambre.etat,
                    "est_active": chambre.est_active,
                },
            )

            messages.success(
                request,
                "La chambre a été modifiée avec succès.",
            )

            return redirect(
                "hebergement:liste_chambres"
            )

    else:
        formulaire = ChambreForm(
            instance=chambre
        )

    return render(
        request,
        "hebergement/responsable/chambres/formulaire.html",
        {
            "formulaire": formulaire,
            "chambre": chambre,
            "titre_page": "Modifier une chambre",
            "bouton_validation": "Enregistrer",
        },
    )


# ============================================================
# RESPONSABLE — CHANGER L'ÉTAT D'UNE CHAMBRE
# ============================================================

@login_required
@transaction.atomic
# ============================================================
# RESPONSABLE — CHANGER L’ÉTAT D’UNE CHAMBRE
# ============================================================

@login_required
@transaction.atomic
def changer_etat_chambre(request, chambre_id):
    utilisateur = verifier_responsable(request)

    chambre = get_object_or_404(
        Chambre.objects
        .select_for_update()
        .select_related(
            "batiment",
        )
        .prefetch_related(
            "affectations",
        ),
        pk=chambre_id,
    )

    if request.method != "POST":
        messages.error(
            request,
            "Cette action doit être effectuée depuis le formulaire.",
        )

        return redirect(
            "hebergement:liste_chambres"
        )

    nouvel_etat = request.POST.get(
        "etat",
        "",
    ).strip()

    etats_autorises = {
        Chambre.Etat.DISPONIBLE,
        Chambre.Etat.MAINTENANCE,
        Chambre.Etat.HORS_SERVICE,
    }

    if nouvel_etat not in etats_autorises:
        messages.error(
            request,
            "L’état demandé est invalide.",
        )

        return redirect(
            "hebergement:liste_chambres"
        )

    if nouvel_etat == chambre.etat:
        messages.info(
            request,
            (
                "La chambre possède déjà l’état "
                f"« {chambre.get_etat_display()} »."
            ),
        )

        return redirect(
            "hebergement:liste_chambres"
        )

    nombre_occupants = Affectation.objects.filter(
        chambre=chambre,
        statut=Affectation.Statut.ACTIVE,
    ).count()

    # ========================================================
    # MAINTENANCE OU HORS SERVICE
    # ========================================================

    if (
        nouvel_etat
        in {
            Chambre.Etat.MAINTENANCE,
            Chambre.Etat.HORS_SERVICE,
        }
        and nombre_occupants > 0
    ):
        messages.error(
            request,
            (
                "Cette chambre contient encore "
                f"{nombre_occupants} étudiant(s). "
                "Transférez ou clôturez leurs affectations "
                "avant de changer son état."
            ),
        )

        return redirect(
            "hebergement:liste_chambres"
        )

    # ========================================================
    # RÉACTIVATION
    # ========================================================

    if nouvel_etat == Chambre.Etat.DISPONIBLE:
        if chambre.batiment.statut != Batiment.Statut.ACTIF:
            messages.error(
                request,
                (
                    "Cette chambre ne peut pas être réactivée, "
                    "car son bâtiment n’est pas actif."
                ),
            )

            return redirect(
                "hebergement:liste_chambres"
            )

        if chambre.capacite <= 0:
            messages.error(
                request,
                (
                    "Cette chambre possède une capacité invalide "
                    "et ne peut pas être réactivée."
                ),
            )

            return redirect(
                "hebergement:liste_chambres"
            )

    etat_avant_modification = chambre.etat
    activation_avant_modification = chambre.est_active

    chambre.etat = nouvel_etat

    if nouvel_etat == Chambre.Etat.HORS_SERVICE:
        chambre.est_active = False
    else:
        chambre.est_active = True

    chambre.full_clean(
        exclude=[
            "batiment",
            "numero",
            "etage",
            "capacite",
            "type_chambre",
            "description",
        ]
    )

    chambre.save(
        update_fields=[
            "etat",
            "est_active",
            "date_modification",
        ]
    )

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="Chambre",
        identifiant_entite=chambre.pk,
        description=(
            f"Changement de l’état de la chambre "
            f"{chambre.batiment.code}/"
            f"{chambre.numero} : "
            f"{chambre.get_etat_display()}."
        ),
        request=request,
        anciennes_valeurs={
            "etat": etat_avant_modification,
            "est_active": activation_avant_modification,
        },
        nouvelles_valeurs={
            "etat": chambre.etat,
            "est_active": chambre.est_active,
        },
    )

    messages.success(
        request,
        (
            "L’état de la chambre a été "
            "mis à jour avec succès."
        ),
    )

    return redirect(
        "hebergement:liste_chambres"
    )
# ============================================================
# RESPONSABLE — LISTE DES ANNÉES UNIVERSITAIRES
# ============================================================

@login_required
def liste_annees_universitaires(request):
    verifier_responsable(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    annees = (
        AnneeUniversitaire.objects
        .prefetch_related(
            "demandes_hebergement",
            "affectations",
        )
        .order_by("-date_debut")
    )

    # ========================================================
    # RECHERCHE
    # ========================================================

    if recherche:
        annees = annees.filter(
            Q(libelle__icontains=recherche)
        )

    # ========================================================
    # FILTRE PAR STATUT
    # ========================================================

    valeurs_statuts = {
        valeur
        for valeur, libelle
        in AnneeUniversitaire.Statut.choices
    }

    if (
        statut_selectionne
        and statut_selectionne in valeurs_statuts
    ):
        annees = annees.filter(
            statut=statut_selectionne,
        )

    # ========================================================
    # CALCULS POUR CHAQUE ANNÉE
    # ========================================================

    annees = list(annees)

    for annee in annees:
        demandes = list(
            annee.demandes_hebergement.all()
        )

        affectations = list(
            annee.affectations.all()
        )

        annee.nombre_demandes_calcule = len(
            demandes
        )

        annee.nombre_demandes_acceptees_calcule = sum(
            1
            for demande in demandes
            if demande.statut
            == DemandeHebergement.Statut.ACCEPTEE
        )

        annee.nombre_demandes_refusees_calcule = sum(
            1
            for demande in demandes
            if demande.statut
            == DemandeHebergement.Statut.REFUSEE
        )

        annee.nombre_demandes_en_attente_calcule = sum(
            1
            for demande in demandes
            if demande.statut
            in {
                DemandeHebergement.Statut.SOUMISE,
                DemandeHebergement.Statut.EN_ETUDE,
                DemandeHebergement.Statut.LISTE_ATTENTE,
            }
        )

        annee.nombre_affectations_calcule = len(
            affectations
        )

        annee.nombre_affectations_prevues_calcule = sum(
            1
            for affectation in affectations
            if affectation.statut
            == Affectation.Statut.PREVUE
        )

        annee.nombre_affectations_actives_calcule = sum(
            1
            for affectation in affectations
            if affectation.statut
            == Affectation.Statut.ACTIVE
        )

        annee.nombre_affectations_cloturees_calcule = sum(
            1
            for affectation in affectations
            if affectation.statut
            == Affectation.Statut.CLOTUREE
        )

        annee.nombre_affectations_ouvertes_calcule = (
            annee.nombre_affectations_prevues_calcule
            + annee.nombre_affectations_actives_calcule
        )

        duree = (
            annee.date_fin
            - annee.date_debut
        )

        annee.duree_jours_calculee = (
            duree.days + 1
        )

        aujourd_hui = timezone.localdate()

        if aujourd_hui < annee.date_debut:
            annee.situation_temporelle = "A_VENIR"

        elif aujourd_hui > annee.date_fin:
            annee.situation_temporelle = "TERMINEE"

        else:
            annee.situation_temporelle = "EN_COURS"

    # ========================================================
    # STATISTIQUES GLOBALES
    # ========================================================

    annees_globales = (
        AnneeUniversitaire.objects.all()
    )

    nombre_total_global = (
        annees_globales.count()
    )

    nombre_planifiees = (
        annees_globales
        .filter(
            statut=(
                AnneeUniversitaire
                .Statut
                .PLANIFIEE
            ),
        )
        .count()
    )

    nombre_actives = (
        annees_globales
        .filter(
            statut=(
                AnneeUniversitaire
                .Statut
                .ACTIVE
            ),
        )
        .count()
    )

    nombre_cloturees = (
        annees_globales
        .filter(
            statut=(
                AnneeUniversitaire
                .Statut
                .CLOTUREE
            ),
        )
        .count()
    )

    annee_active = (
        annees_globales
        .filter(
            statut=(
                AnneeUniversitaire
                .Statut
                .ACTIVE
            ),
        )
        .first()
    )

    total_demandes = (
        DemandeHebergement.objects.count()
    )

    total_affectations = (
        Affectation.objects.count()
    )

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        annees,
        10,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )

    parametres_filtres = request.GET.copy()

    if "page" in parametres_filtres:
        parametres_filtres.pop("page")

    chaine_filtres = (
        parametres_filtres.urlencode()
    )

    contexte = {
        "annees": page_obj,
        "page_obj": page_obj,

        "recherche": recherche,
        "statut_selectionne": statut_selectionne,

        "choix_statuts": (
            AnneeUniversitaire.Statut.choices
        ),

        "nombre_annees": paginator.count,
        "nombre_total_global": nombre_total_global,
        "nombre_planifiees": nombre_planifiees,
        "nombre_actives": nombre_actives,
        "nombre_cloturees": nombre_cloturees,

        "annee_active": annee_active,
        "total_demandes": total_demandes,
        "total_affectations": total_affectations,

        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        "hebergement/responsable/annees/liste.html",
        contexte,
    )


# ============================================================
# RESPONSABLE — CRÉER UNE ANNÉE UNIVERSITAIRE
# ============================================================

@login_required
@transaction.atomic
def creer_annee_universitaire(request):
    utilisateur = verifier_responsable(request)

    if request.method == "POST":
        formulaire = AnneeUniversitaireForm(
            request.POST
        )

        if formulaire.is_valid():
            annee = formulaire.save(commit=False)

            try:
                annee.save()

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
                    entite="AnneeUniversitaire",
                    identifiant_entite=annee.pk,
                    description=(
                        "Création de l'année universitaire "
                        f"{annee.libelle}."
                    ),
                    request=request,
                    nouvelles_valeurs={
                        "libelle": annee.libelle,
                        "date_debut": str(
                            annee.date_debut
                        ),
                        "date_fin": str(
                            annee.date_fin
                        ),
                        "statut": annee.statut,
                    },
                )

                messages.success(
                    request,
                    (
                        "L'année universitaire a été "
                        "créée avec succès."
                    ),
                )

                return redirect(
                    "hebergement:"
                    "liste_annees_universitaires"
                )

    else:
        formulaire = AnneeUniversitaireForm(
            initial={
                "statut": (
                    AnneeUniversitaire
                    .Statut
                    .PLANIFIEE
                )
            }
        )

    return render(
        request,
        "hebergement/responsable/annees/formulaire.html",
        {
            "formulaire": formulaire,
            "titre_page": (
                "Ajouter une année universitaire"
            ),
            "bouton_validation": (
                "Créer l'année universitaire"
            ),
        },
    )


# ============================================================
# RESPONSABLE — MODIFIER UNE ANNÉE UNIVERSITAIRE
# ============================================================

@login_required
@transaction.atomic
def modifier_annee_universitaire(
    request,
    annee_id,
):
    utilisateur = verifier_responsable(request)

    annee = get_object_or_404(
        AnneeUniversitaire.objects.select_for_update(),
        pk=annee_id,
    )

    valeurs_avant_modification = {
        "libelle": annee.libelle,
        "date_debut": str(annee.date_debut),
        "date_fin": str(annee.date_fin),
        "statut": annee.statut,
    }

    if request.method == "POST":
        formulaire = AnneeUniversitaireForm(
            request.POST,
            instance=annee,
        )

        if formulaire.is_valid():
            annee_modifiee = formulaire.save(
                commit=False
            )

            try:
                annee_modifiee.save()

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
                        HistoriqueAction
                        .TypeAction
                        .MODIFICATION
                    ),
                    entite="AnneeUniversitaire",
                    identifiant_entite=annee.pk,
                    description=(
                        "Modification de l'année "
                        f"universitaire {annee.libelle}."
                    ),
                    request=request,
                    anciennes_valeurs=(
                        valeurs_avant_modification
                    ),
                    nouvelles_valeurs={
                        "libelle": annee.libelle,
                        "date_debut": str(
                            annee.date_debut
                        ),
                        "date_fin": str(
                            annee.date_fin
                        ),
                        "statut": annee.statut,
                    },
                )

                messages.success(
                    request,
                    (
                        "L'année universitaire a été "
                        "modifiée avec succès."
                    ),
                )

                return redirect(
                    "hebergement:"
                    "liste_annees_universitaires"
                )

    else:
        formulaire = AnneeUniversitaireForm(
            instance=annee
        )

    return render(
        request,
        "hebergement/responsable/annees/formulaire.html",
        {
            "formulaire": formulaire,
            "annee": annee,
            "titre_page": (
                "Modifier l'année universitaire"
            ),
            "bouton_validation": "Enregistrer",
        },
    )


# ============================================================
# RESPONSABLE — ACTIVER UNE ANNÉE UNIVERSITAIRE
# ============================================================

@login_required
@transaction.atomic
def activer_annee_universitaire(
    request,
    annee_id,
):
    utilisateur = verifier_responsable(request)

    if request.method != "POST":
        messages.error(
            request,
            "Cette action doit être effectuée depuis le formulaire.",
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # Verrouillage des années pour éviter deux activations
    # simultanées.
    annees_verrouillees = (
        AnneeUniversitaire.objects
        .select_for_update()
        .order_by("pk")
    )

    annee = get_object_or_404(
        annees_verrouillees,
        pk=annee_id,
    )

    # ========================================================
    # ANNÉE DÉJÀ ACTIVE
    # ========================================================

    if (
        annee.statut
        == AnneeUniversitaire.Statut.ACTIVE
    ):
        messages.info(
            request,
            (
                f"L’année universitaire {annee.libelle} "
                "est déjà active."
            ),
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # ANNÉE CLÔTURÉE
    # ========================================================

    if (
        annee.statut
        == AnneeUniversitaire.Statut.CLOTUREE
    ):
        messages.error(
            request,
            (
                "Une année universitaire clôturée "
                "ne peut pas être réactivée."
            ),
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # RECHERCHE D’UNE AUTRE ANNÉE ACTIVE
    # ========================================================

    ancienne_annee_active = (
        annees_verrouillees
        .filter(
            statut=AnneeUniversitaire.Statut.ACTIVE,
        )
        .exclude(
            pk=annee.pk,
        )
        .first()
    )

    if ancienne_annee_active:
        affectations_ouvertes = (
            Affectation.objects
            .filter(
                annee_universitaire=ancienne_annee_active,
                statut__in={
                    Affectation.Statut.PREVUE,
                    Affectation.Statut.ACTIVE,
                },
            )
            .count()
        )

        if affectations_ouvertes > 0:
            messages.error(
                request,
                (
                    f"L’année {ancienne_annee_active.libelle} "
                    "est encore active et contient "
                    f"{affectations_ouvertes} affectation(s) "
                    "prévue(s) ou active(s). "
                    "Clôturez ces affectations avant "
                    "d’activer une nouvelle année."
                ),
            )

            return redirect(
                "hebergement:liste_annees_universitaires"
            )

        messages.error(
            request,
            (
                f"L’année {ancienne_annee_active.libelle} "
                "est actuellement active. "
                "Clôturez-la avant d’activer "
                f"l’année {annee.libelle}."
            ),
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # ACTIVATION
    # ========================================================

    statut_avant_activation = annee.statut

    annee.statut = (
        AnneeUniversitaire.Statut.ACTIVE
    )

    try:
        annee.full_clean()
        annee.save(
            update_fields=[
                "statut",
                "date_modification",
            ]
        )

    except ValidationError as erreur:
        message_erreur = (
            " ".join(erreur.messages)
            if hasattr(erreur, "messages")
            else str(erreur)
        )

        messages.error(
            request,
            message_erreur,
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # HISTORIQUE
    # ========================================================

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="AnneeUniversitaire",
        identifiant_entite=annee.pk,
        description=(
            "Activation de l’année universitaire "
            f"{annee.libelle}."
        ),
        request=request,
        anciennes_valeurs={
            "statut": statut_avant_activation,
        },
        nouvelles_valeurs={
            "statut": annee.statut,
        },
    )

    messages.success(
        request,
        (
            f"L’année universitaire {annee.libelle} "
            "est maintenant active."
        ),
    )

    return redirect(
        "hebergement:liste_annees_universitaires"
    )


# ============================================================
# RESPONSABLE — CLÔTURER UNE ANNÉE UNIVERSITAIRE
# ============================================================

@login_required
@transaction.atomic
def cloturer_annee_universitaire(
    request,
    annee_id,
):
    utilisateur = verifier_responsable(request)

    if request.method != "POST":
        messages.error(
            request,
            "Cette action doit être effectuée depuis le formulaire.",
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    annee = get_object_or_404(
        AnneeUniversitaire.objects
        .select_for_update(),
        pk=annee_id,
    )

    # ========================================================
    # ANNÉE DÉJÀ CLÔTURÉE
    # ========================================================

    if (
        annee.statut
        == AnneeUniversitaire.Statut.CLOTUREE
    ):
        messages.info(
            request,
            (
                f"L’année universitaire {annee.libelle} "
                "est déjà clôturée."
            ),
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # ANNÉE PLANIFIÉE
    # ========================================================

    if (
        annee.statut
        == AnneeUniversitaire.Statut.PLANIFIEE
    ):
        messages.error(
            request,
            (
                "Une année universitaire planifiée ne peut "
                "pas être clôturée directement. "
                "Elle doit d’abord être activée."
            ),
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # AFFECTATIONS OUVERTES
    # ========================================================

    affectations_ouvertes = (
        Affectation.objects
        .filter(
            annee_universitaire=annee,
            statut__in={
                Affectation.Statut.PREVUE,
                Affectation.Statut.ACTIVE,
            },
        )
    )

    nombre_affectations_ouvertes = (
        affectations_ouvertes.count()
    )

    if nombre_affectations_ouvertes > 0:
        messages.error(
            request,
            (
                f"Cette année contient encore "
                f"{nombre_affectations_ouvertes} "
                "affectation(s) prévue(s) ou active(s). "
                "Clôturez-les avant de clôturer l’année."
            ),
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # CLÔTURE
    # ========================================================

    statut_avant_cloture = annee.statut

    annee.statut = (
        AnneeUniversitaire.Statut.CLOTUREE
    )

    try:
        annee.full_clean()

        annee.save(
            update_fields=[
                "statut",
                "date_modification",
            ]
        )

    except ValidationError as erreur:
        message_erreur = (
            " ".join(erreur.messages)
            if hasattr(erreur, "messages")
            else str(erreur)
        )

        messages.error(
            request,
            message_erreur,
        )

        return redirect(
            "hebergement:liste_annees_universitaires"
        )

    # ========================================================
    # HISTORIQUE
    # ========================================================

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.CLOTURE
        ),
        entite="AnneeUniversitaire",
        identifiant_entite=annee.pk,
        description=(
            "Clôture de l’année universitaire "
            f"{annee.libelle}."
        ),
        request=request,
        anciennes_valeurs={
            "statut": statut_avant_cloture,
        },
        nouvelles_valeurs={
            "statut": annee.statut,
        },
    )

    messages.success(
        request,
        (
            f"L’année universitaire {annee.libelle} "
            "a été clôturée avec succès."
        ),
    )

    return redirect(
        "hebergement:liste_annees_universitaires"
    )
# ============================================================
# RESPONSABLE — VALIDER OU REJETER UN JUSTIFICATIF
# ============================================================

@login_required
@transaction.atomic
def valider_justificatif(request, justificatif_id):
    utilisateur = verifier_responsable(request)

    justificatif = get_object_or_404(
        Justificatif.objects
        .select_for_update()
        .select_related(
            "demande",
            "demande__etudiant",
            "demande__etudiant__utilisateur",
        ),
        pk=justificatif_id,
    )

    if request.method != "POST":
        return redirect(
            "hebergement:detail_demande_responsable",
            demande_id=justificatif.demande_id,
        )

    action = request.POST.get("action", "").strip()
    commentaire_validation = request.POST.get(
        "commentaire_validation",
        "",
    ).strip()

    if action not in {"valider", "refuser"}:
        messages.error(request, "L'action demandée est invalide.")
        return redirect(
            "hebergement:detail_demande_responsable",
            demande_id=justificatif.demande_id,
        )

    if action == "refuser" and not commentaire_validation:
        messages.error(request, "Le motif du rejet est obligatoire.")
        return redirect(
            "hebergement:detail_demande_responsable",
            demande_id=justificatif.demande_id,
        )

    ancien_statut = justificatif.statut_validation
    ancien_commentaire = justificatif.commentaire_validation

    if action == "valider":
        justificatif.statut_validation = Justificatif.StatutValidation.VALIDE
        justificatif.commentaire_validation = commentaire_validation
        titre_notification = "Pièce justificative validée"
        message_notification = (
            "Votre document « "
            f"{justificatif.get_type_document_display()} » "
            "a été validé par l'administration."
        )
        message_succes = "La pièce justificative a été validée."
    else:
        justificatif.statut_validation = Justificatif.StatutValidation.REJETE
        justificatif.commentaire_validation = commentaire_validation
        titre_notification = "Pièce justificative rejetée"
        message_notification = (
            "Votre document « "
            f"{justificatif.get_type_document_display()} » "
            f"a été rejeté. Motif : {commentaire_validation}"
        )
        message_succes = "La pièce justificative a été rejetée."

    justificatif.date_validation = timezone.now()
    justificatif.full_clean()
    justificatif.save()

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.VALIDATION
            if action == "valider"
            else HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="Justificatif",
        identifiant_entite=justificatif.pk,
        description=(
            "Traitement du justificatif "
            f"{justificatif.get_type_document_display()} "
            "de l'étudiant "
            f"{justificatif.demande.etudiant.matricule}."
        ),
        request=request,
        anciennes_valeurs={
            "statut_validation": ancien_statut,
            "commentaire_validation": ancien_commentaire,
        },
        nouvelles_valeurs={
            "statut_validation": justificatif.statut_validation,
            "commentaire_validation": justificatif.commentaire_validation,
        },
    )

    creer_notification(
        utilisateur=justificatif.demande.etudiant.utilisateur,
        titre=titre_notification,
        message=message_notification,
        type_notification=(
    Notification.TypeNotification.DEMANDE
),
        lien=f"/hebergement/demande/{justificatif.demande_id}/",
    )

    messages.success(request, message_succes)

    return redirect(
        "hebergement:detail_demande_responsable",
        demande_id=justificatif.demande_id,
    )

@login_required
@transaction.atomic
def remettre_justificatif_en_attente(
    request,
    justificatif_id,
):
    utilisateur = verifier_responsable(request)

    justificatif = get_object_or_404(
        Justificatif.objects
        .select_for_update()
        .select_related(
            "demande",
            "demande__etudiant",
            "demande__etudiant__utilisateur",
        ),
        pk=justificatif_id,
    )

    url_detail = (
        "hebergement:detail_demande_responsable"
    )

    if request.method != "POST":
        messages.error(
            request,
            (
                "Cette action doit être effectuée "
                "depuis le formulaire prévu."
            ),
        )

        return redirect(
            url_detail,
            demande_id=justificatif.demande_id,
        )

    if (
        justificatif.statut_validation
        == Justificatif.StatutValidation.EN_ATTENTE
    ):
        messages.info(
            request,
            (
                "Ce justificatif est déjà "
                "en attente de validation."
            ),
        )

        return redirect(
            url_detail,
            demande_id=justificatif.demande_id,
        )

    ancien_statut = (
        justificatif.statut_validation
    )

    ancien_commentaire = (
        justificatif.commentaire_validation
    )

    ancienne_date_validation = (
        justificatif.date_validation
    )

    try:
        justificatif.remettre_en_attente()

    except ValidationError as erreur:
        if hasattr(erreur, "message_dict"):
            messages_erreurs = []

            for erreurs in erreur.message_dict.values():
                messages_erreurs.extend(erreurs)

            message_erreur = " ".join(
                messages_erreurs
            )

        else:
            message_erreur = " ".join(
                erreur.messages
            )

        messages.error(
            request,
            message_erreur,
        )

        transaction.set_rollback(True)

        return redirect(
            url_detail,
            demande_id=justificatif.demande_id,
        )

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur,
        type_action=(
            HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="Justificatif",
        identifiant_entite=justificatif.pk,
        description=(
            "Remise en attente du justificatif "
            f"{justificatif.get_type_document_display()} "
            "de l’étudiant "
            f"{justificatif.demande.etudiant.matricule}."
        ),
        request=request,
        anciennes_valeurs={
            "statut_validation": ancien_statut,
            "commentaire_validation": (
                ancien_commentaire
            ),
            "date_validation": (
                str(ancienne_date_validation)
                if ancienne_date_validation
                else None
            ),
        },
        nouvelles_valeurs={
            "statut_validation": (
                justificatif.statut_validation
            ),
            "commentaire_validation": "",
            "date_validation": None,
        },
    )

    creer_notification(
        utilisateur=(
            justificatif
            .demande
            .etudiant
            .utilisateur
        ),
        titre="Justificatif à vérifier",
        message=(
            "Votre document « "
            f"{justificatif.get_type_document_display()} » "
            "a été remis en attente de validation."
        ),
        type_notification=(
    Notification.TypeNotification.DEMANDE
),
        lien=(
            f"/hebergement/demande/"
            f"{justificatif.demande_id}/"
        ),
    )

    messages.success(
        request,
        (
            "Le justificatif a été remis "
            "en attente avec succès."
        ),
    )

    return redirect(
        url_detail,
        demande_id=justificatif.demande_id,
    )
@login_required
def mon_hebergement(request):
    etudiant = obtenir_profil_etudiant(request)

    affectations = (
        Affectation.objects
        .filter(etudiant=etudiant)
        .select_related(
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
            "demande_hebergement",
        )
        .order_by("-date_creation")
    )

    affectation_actuelle = (
        affectations
        .filter(
            statut__in=[
                Affectation.Statut.ACTIVE,
                Affectation.Statut.PREVUE,
            ]
        )
        .first()
    )

    historique_affectations = affectations.exclude(
        statut__in=[
            Affectation.Statut.ACTIVE,
            Affectation.Statut.PREVUE,
        ]
    )

    contexte = {
        "etudiant": etudiant,
        "affectation_actuelle": affectation_actuelle,
        "historique_affectations": historique_affectations,
    }

    return render(
        request,
        "hebergement/etudiant/mon_hebergement.html",
        contexte,
    )