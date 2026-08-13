from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from accounts.models import Utilisateur
from audit.models import HistoriqueAction

from .forms import (
    EtudiantForm,
    ProfilEtudiantPersonnelForm,
)
from .models import Etudiant


# ============================================================
# CONTRÔLE D'ACCÈS
# ============================================================

def verifier_gestionnaire_etudiants(request):
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
            "Vous n'êtes pas autorisé à gérer les étudiants."
        )

    return utilisateur


# ============================================================
# LISTE DES ÉTUDIANTS
# ============================================================

@login_required
def liste_etudiants(request):
    verifier_gestionnaire_etudiants(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    statut_selectionne = request.GET.get(
        "statut",
        "",
    ).strip()

    filiere_selectionnee = request.GET.get(
        "filiere",
        "",
    ).strip()

    niveau_selectionne = request.GET.get(
        "niveau",
        "",
    ).strip()

    sexe_selectionne = request.GET.get(
        "sexe",
        "",
    ).strip()

    compte_selectionne = request.GET.get(
        "compte",
        "",
    ).strip()

    etudiants = (
        Etudiant.objects
        .select_related("utilisateur")
        .order_by(
            "utilisateur__last_name",
            "utilisateur__first_name",
            "matricule",
        )
    )

    # ========================================================
    # RECHERCHE TEXTUELLE
    # ========================================================

    if recherche:
        etudiants = etudiants.filter(
            Q(matricule__icontains=recherche)
            | Q(cne__icontains=recherche)
            | Q(filiere__icontains=recherche)
            | Q(niveau_etude__icontains=recherche)
            | Q(ville_origine__icontains=recherche)
            | Q(utilisateur__username__icontains=recherche)
            | Q(utilisateur__first_name__icontains=recherche)
            | Q(utilisateur__last_name__icontains=recherche)
            | Q(utilisateur__email__icontains=recherche)
        ).distinct()

    # ========================================================
    # FILTRE PAR STATUT
    # ========================================================

    valeurs_statuts = {
        valeur
        for valeur, libelle
        in Etudiant.Statut.choices
    }

    if (
        statut_selectionne
        and statut_selectionne in valeurs_statuts
    ):
        etudiants = etudiants.filter(
            statut=statut_selectionne,
        )

    # ========================================================
    # FILTRE PAR FILIÈRE
    # ========================================================

    if filiere_selectionnee:
        etudiants = etudiants.filter(
            filiere=filiere_selectionnee,
        )

    # ========================================================
    # FILTRE PAR NIVEAU
    # ========================================================

    if niveau_selectionne:
        etudiants = etudiants.filter(
            niveau_etude=niveau_selectionne,
        )

    # ========================================================
    # FILTRE PAR SEXE
    # ========================================================

    valeurs_sexes = {
        valeur
        for valeur, libelle
        in Etudiant.Sexe.choices
    }

    if (
        sexe_selectionne
        and sexe_selectionne in valeurs_sexes
    ):
        etudiants = etudiants.filter(
            sexe=sexe_selectionne,
        )

    # ========================================================
    # FILTRE PAR ÉTAT DU COMPTE
    # ========================================================

    if compte_selectionne == "ACTIF":
        etudiants = etudiants.filter(
            utilisateur__is_active=True,
        )

    elif compte_selectionne == "INACTIF":
        etudiants = etudiants.filter(
            utilisateur__is_active=False,
        )

    # ========================================================
    # VALEURS DES LISTES DE FILTRES
    # ========================================================

    filieres = (
        Etudiant.objects
        .exclude(filiere="")
        .values_list(
            "filiere",
            flat=True,
        )
        .distinct()
        .order_by("filiere")
    )

    niveaux = (
        Etudiant.objects
        .exclude(niveau_etude="")
        .values_list(
            "niveau_etude",
            flat=True,
        )
        .distinct()
        .order_by("niveau_etude")
    )

    # ========================================================
    # STATISTIQUES GLOBALES
    # ========================================================

    etudiants_globaux = Etudiant.objects.select_related(
        "utilisateur"
    )

    nombre_total_global = etudiants_globaux.count()

    nombre_actifs = etudiants_globaux.filter(
        statut=Etudiant.Statut.ACTIF,
    ).count()

    nombre_inactifs = etudiants_globaux.filter(
        statut=Etudiant.Statut.INACTIF,
    ).count()

    nombre_diplomes = etudiants_globaux.filter(
        statut=Etudiant.Statut.DIPLOME,
    ).count()

    nombre_abandons = etudiants_globaux.filter(
        statut=Etudiant.Statut.ABANDON,
    ).count()

    nombre_comptes_actifs = etudiants_globaux.filter(
        utilisateur__is_active=True,
    ).count()

    nombre_comptes_inactifs = etudiants_globaux.filter(
        utilisateur__is_active=False,
    ).count()

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        etudiants,
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
        "etudiants": page_obj,
        "page_obj": page_obj,

        "recherche": recherche,
        "statut_selectionne": statut_selectionne,
        "filiere_selectionnee": filiere_selectionnee,
        "niveau_selectionne": niveau_selectionne,
        "sexe_selectionne": sexe_selectionne,
        "compte_selectionne": compte_selectionne,

        "choix_statuts": Etudiant.Statut.choices,
        "choix_sexes": Etudiant.Sexe.choices,
        "filieres": filieres,
        "niveaux": niveaux,

        "nombre_etudiants": paginator.count,
        "nombre_total_global": nombre_total_global,
        "nombre_actifs": nombre_actifs,
        "nombre_inactifs": nombre_inactifs,
        "nombre_diplomes": nombre_diplomes,
        "nombre_abandons": nombre_abandons,
        "nombre_comptes_actifs": nombre_comptes_actifs,
        "nombre_comptes_inactifs": nombre_comptes_inactifs,

        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        "etudiants/responsable/liste_etudiants.html",
        contexte,
    )


# ============================================================
# CRÉER UN PROFIL ÉTUDIANT
# ============================================================

@login_required
@transaction.atomic
def creer_etudiant(request):
    utilisateur_connecte = (
        verifier_gestionnaire_etudiants(request)
    )

    if request.method == "POST":
        formulaire = EtudiantForm(
            request.POST,
            request.FILES,
        )

        if formulaire.is_valid():
            etudiant = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur_connecte,
                type_action=(
                    HistoriqueAction.TypeAction.CREATION
                ),
                entite="Etudiant",
                identifiant_entite=etudiant.pk,
                description=(
                    "Création du profil étudiant "
                    f"{etudiant.matricule}."
                ),
                request=request,
                nouvelles_valeurs={
                    "utilisateur": (
                        etudiant.utilisateur.username
                    ),
                    "matricule": etudiant.matricule,
                    "cne": etudiant.cne,
                    "filiere": etudiant.filiere,
                    "niveau_etude": (
                        etudiant.niveau_etude
                    ),
                    "statut": etudiant.statut,
                },
            )

            messages.success(
                request,
                (
                    f"Le profil étudiant "
                    f"{etudiant.matricule} "
                    "a été créé avec succès."
                ),
            )

            return redirect(
                "etudiants:detail_etudiant",
                etudiant_id=etudiant.pk,
            )

    else:
        formulaire = EtudiantForm()

    return render(
        request,
        "etudiants/responsable/formulaire_etudiant.html",
        {
            "formulaire": formulaire,
            "titre_page": "Ajouter un étudiant",
            "bouton_validation": (
                "Créer le profil étudiant"
            ),
        },
    )


# ============================================================
# DÉTAIL D'UN ÉTUDIANT
# ============================================================

@login_required
def detail_etudiant(request, etudiant_id):
    verifier_gestionnaire_etudiants(request)

    etudiant = get_object_or_404(
        Etudiant.objects.select_related(
            "utilisateur"
        ),
        pk=etudiant_id,
    )

    demandes = (
        etudiant.demandes_hebergement
        .select_related("annee_universitaire")
        .order_by("-date_creation")[:5]
    )

    affectations = (
        etudiant.affectations
        .select_related(
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
        )
        .order_by("-date_creation")[:5]
    )

    frais = (
        etudiant.frais_hebergement
        .select_related("annee_universitaire")
        .order_by(
            "-annee_universitaire__date_debut"
        )[:5]
    )

    reclamations = (
        etudiant.reclamations
        .select_related(
            "chambre",
            "chambre__batiment",
        )
        .order_by("-date_creation")[:5]
    )

    return render(
        request,
        "etudiants/responsable/detail_etudiant.html",
        {
            "etudiant": etudiant,
            "demandes": demandes,
            "affectations": affectations,
            "frais": frais,
            "reclamations": reclamations,
        },
    )


# ============================================================
# MODIFIER UN ÉTUDIANT
# ============================================================

@login_required
@transaction.atomic
def modifier_etudiant(request, etudiant_id):
    utilisateur_connecte = (
        verifier_gestionnaire_etudiants(request)
    )

    etudiant = get_object_or_404(
        Etudiant.objects
        .select_for_update()
        .select_related("utilisateur"),
        pk=etudiant_id,
    )

    valeurs_avant_modification = {
        "utilisateur": (
            etudiant.utilisateur.username
        ),
        "matricule": etudiant.matricule,
        "cne": etudiant.cne,
        "date_naissance": str(
            etudiant.date_naissance
        ),
        "sexe": etudiant.sexe,
        "adresse": etudiant.adresse,
        "ville_origine": (
            etudiant.ville_origine
        ),
        "filiere": etudiant.filiere,
        "niveau_etude": (
            etudiant.niveau_etude
        ),
        "statut": etudiant.statut,
    }

    if request.method == "POST":
        formulaire = EtudiantForm(
            request.POST,
            request.FILES,
            instance=etudiant,
        )

        if formulaire.is_valid():
            etudiant = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=utilisateur_connecte,
                type_action=(
                    HistoriqueAction
                    .TypeAction
                    .MODIFICATION
                ),
                entite="Etudiant",
                identifiant_entite=etudiant.pk,
                description=(
                    "Modification du profil étudiant "
                    f"{etudiant.matricule}."
                ),
                request=request,
                anciennes_valeurs=(
                    valeurs_avant_modification
                ),
                nouvelles_valeurs={
                    "utilisateur": (
                        etudiant.utilisateur.username
                    ),
                    "matricule": etudiant.matricule,
                    "cne": etudiant.cne,
                    "date_naissance": str(
                        etudiant.date_naissance
                    ),
                    "sexe": etudiant.sexe,
                    "adresse": etudiant.adresse,
                    "ville_origine": (
                        etudiant.ville_origine
                    ),
                    "filiere": etudiant.filiere,
                    "niveau_etude": (
                        etudiant.niveau_etude
                    ),
                    "statut": etudiant.statut,
                },
            )

            messages.success(
                request,
                (
                    "Le profil étudiant a été "
                    "modifié avec succès."
                ),
            )

            return redirect(
                "etudiants:detail_etudiant",
                etudiant_id=etudiant.pk,
            )

    else:
        formulaire = EtudiantForm(
            instance=etudiant
        )

    return render(
        request,
        "etudiants/responsable/formulaire_etudiant.html",
        {
            "formulaire": formulaire,
            "etudiant": etudiant,
            "titre_page": "Modifier un étudiant",
            "bouton_validation": "Enregistrer",
        },
    )


# ============================================================
# ACTIVER OU DÉSACTIVER LE PROFIL ÉTUDIANT
# ============================================================

@login_required
@transaction.atomic
def changer_statut_etudiant(
    request,
    etudiant_id,
):
    utilisateur_connecte = (
        verifier_gestionnaire_etudiants(request)
    )

    etudiant = get_object_or_404(
        Etudiant.objects
        .select_for_update()
        .select_related("utilisateur"),
        pk=etudiant_id,
    )

    if request.method != "POST":
        return redirect(
            "etudiants:detail_etudiant",
            etudiant_id=etudiant.pk,
        )

    nouveau_statut = request.POST.get(
        "statut",
        "",
    ).strip()

    statuts_valides = {
        valeur
        for valeur, _ in Etudiant.Statut.choices
    }

    if nouveau_statut not in statuts_valides:
        messages.error(
            request,
            "Le statut demandé est invalide.",
        )

        return redirect(
            "etudiants:detail_etudiant",
            etudiant_id=etudiant.pk,
        )

    statut_avant_modification = etudiant.statut

    etudiant.statut = nouveau_statut
    etudiant.save(
        update_fields=[
            "statut",
            "date_modification",
        ]
    )

    HistoriqueAction.enregistrer_action(
        utilisateur=utilisateur_connecte,
        type_action=(
            HistoriqueAction.TypeAction.MODIFICATION
        ),
        entite="Etudiant",
        identifiant_entite=etudiant.pk,
        description=(
            "Modification du statut du profil étudiant "
            f"{etudiant.matricule}."
        ),
        request=request,
        anciennes_valeurs={
            "statut": statut_avant_modification,
        },
        nouvelles_valeurs={
            "statut": etudiant.statut,
        },
    )

    messages.success(
        request,
        "Le statut de l'étudiant a été mis à jour.",
    )

    return redirect(
        "etudiants:detail_etudiant",
        etudiant_id=etudiant.pk,
    )


def verifier_etudiant_connecte(request):
    utilisateur = request.user

    if (
        not utilisateur.is_authenticated
        or not utilisateur.is_active
        or utilisateur.role
        != Utilisateur.Role.ETUDIANT
    ):
        raise PermissionDenied(
            "Cette page est réservée aux étudiants."
        )

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


@login_required
def mon_profil(request):
    profil = verifier_etudiant_connecte(request)

    return render(
        request,
        "etudiants/etudiant/mon_profil.html",
        {
            "profil": profil,
        },
    )


@login_required
@transaction.atomic
def modifier_mon_profil(request):
    profil = verifier_etudiant_connecte(request)

    anciennes_valeurs = {
        "prenom": profil.utilisateur.first_name,
        "nom": profil.utilisateur.last_name,
        "email": profil.utilisateur.email,
        "date_naissance": str(
            profil.date_naissance
        ),
        "sexe": profil.sexe,
        "adresse": profil.adresse,
        "ville_origine": profil.ville_origine,
    }

    if request.method == "POST":
        formulaire = ProfilEtudiantPersonnelForm(
            request.POST,
            instance=profil,
        )

        if formulaire.is_valid():
            profil = formulaire.save()

            HistoriqueAction.enregistrer_action(
                utilisateur=request.user,
                type_action=(
                    HistoriqueAction
                    .TypeAction
                    .MODIFICATION
                ),
                entite="Etudiant",
                identifiant_entite=profil.pk,
                description=(
                    "Mise à jour de ses informations "
                    f"personnelles par l'étudiant "
                    f"{profil.matricule}."
                ),
                request=request,
                anciennes_valeurs=anciennes_valeurs,
                nouvelles_valeurs={
                    "prenom": (
                        profil.utilisateur.first_name
                    ),
                    "nom": (
                        profil.utilisateur.last_name
                    ),
                    "email": (
                        profil.utilisateur.email
                    ),
                    "date_naissance": str(
                        profil.date_naissance
                    ),
                    "sexe": profil.sexe,
                    "adresse": profil.adresse,
                    "ville_origine": (
                        profil.ville_origine
                    ),
                },
            )

            messages.success(
                request,
                "Vos informations ont été mises à jour.",
            )

            return redirect(
                "etudiants:mon_profil"
            )

    else:
        formulaire = ProfilEtudiantPersonnelForm(
            instance=profil,
        )

    return render(
        request,
        (
            "etudiants/etudiant/"
            "modifier_mon_profil.html"
        ),
        {
            "profil": profil,
            "formulaire": formulaire,
        },
    )
