from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Utilisateur

from .models import HistoriqueAction


# ============================================================
# CONTRÔLE D'ACCÈS
# ============================================================

def verifier_acces_audit(request):
    """
    L'historique est accessible :
    - au superutilisateur ;
    - à l'administrateur ;
    - au responsable de l'internat.
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
            "Vous n'êtes pas autorisé à consulter "
            "l'historique des opérations."
        )

    return utilisateur


# ============================================================
# OUTILS DE COMPATIBILITÉ
# ============================================================

def obtenir_nom_champ_date():
    """
    Rend la vue compatible avec plusieurs noms possibles
    pour le champ d'horodatage du modèle HistoriqueAction.
    """
    noms_champs = {
        champ.name
        for champ in HistoriqueAction._meta.get_fields()
        if hasattr(champ, "name")
    }

    candidats = (
        "date_action",
        "date_creation",
        "date_enregistrement",
        "horodatage",
        "created_at",
        "date",
    )

    for candidat in candidats:
        if candidat in noms_champs:
            return candidat

    return None


def obtenir_nom_champ_ip():
    noms_champs = {
        champ.name
        for champ in HistoriqueAction._meta.get_fields()
        if hasattr(champ, "name")
    }

    for candidat in (
        "adresse_ip",
        "ip",
        "ip_address",
    ):
        if candidat in noms_champs:
            return candidat

    return None


def obtenir_choix_types():
    """
    Utilise les TextChoices du modèle lorsqu'ils existent.
    Sinon, reconstruit la liste depuis les valeurs présentes
    en base.
    """
    type_action = getattr(
        HistoriqueAction,
        "TypeAction",
        None,
    )

    if type_action is not None and hasattr(
        type_action,
        "choices",
    ):
        return list(type_action.choices)

    valeurs = (
        HistoriqueAction.objects
        .exclude(type_action="")
        .values_list(
            "type_action",
            flat=True,
        )
        .distinct()
        .order_by("type_action")
    )

    return [
        (
            valeur,
            str(valeur)
            .replace("_", " ")
            .title(),
        )
        for valeur in valeurs
    ]


def normaliser_valeurs(valeurs):
    """
    Transforme les anciennes/nouvelles valeurs en liste
    prête à être affichée dans le template.
    """
    if not valeurs:
        return []

    if isinstance(valeurs, dict):
        return [
            (str(cle), valeur)
            for cle, valeur in valeurs.items()
        ]

    if isinstance(valeurs, (list, tuple)):
        return [
            (
                f"Élément {index}",
                valeur,
            )
            for index, valeur
            in enumerate(valeurs, start=1)
        ]

    return [
        ("Valeur", valeurs),
    ]


def obtenir_libelle_type(action):
    methode = getattr(
        action,
        "get_type_action_display",
        None,
    )

    if callable(methode):
        try:
            return methode()
        except Exception:
            pass

    return (
        str(action.type_action)
        .replace("_", " ")
        .title()
    )


# ============================================================
# HISTORIQUE DES ACTIONS
# ============================================================

@login_required
def historique_actions(request):
    verifier_acces_audit(request)

    recherche = request.GET.get(
        "recherche",
        "",
    ).strip()

    type_selectionne = request.GET.get(
        "type",
        "",
    ).strip()

    entite_selectionnee = request.GET.get(
        "entite",
        "",
    ).strip()

    utilisateur_selectionne = request.GET.get(
        "utilisateur",
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

    nom_champ_date = obtenir_nom_champ_date()
    nom_champ_ip = obtenir_nom_champ_ip()

    actions = (
        HistoriqueAction.objects
        .select_related("utilisateur")
    )

    if nom_champ_date:
        actions = actions.order_by(
            f"-{nom_champ_date}",
            "-pk",
        )
    else:
        actions = actions.order_by("-pk")

    # ========================================================
    # RECHERCHE
    # ========================================================

    if recherche:
        actions = actions.filter(
            Q(
                description__icontains=recherche
            )
            | Q(
                entite__icontains=recherche
            )
            | Q(
                type_action__icontains=recherche
            )
            | Q(
                utilisateur__username__icontains=recherche
            )
            | Q(
                utilisateur__first_name__icontains=recherche
            )
            | Q(
                utilisateur__last_name__icontains=recherche
            )
        ).distinct()

    # ========================================================
    # FILTRE PAR TYPE
    # ========================================================

    valeurs_types = {
        valeur
        for valeur, _ in obtenir_choix_types()
    }

    if (
        type_selectionne
        and type_selectionne in valeurs_types
    ):
        actions = actions.filter(
            type_action=type_selectionne
        )

    # ========================================================
    # FILTRE PAR ENTITÉ
    # ========================================================

    if entite_selectionnee:
        actions = actions.filter(
            entite=entite_selectionnee
        )

    # ========================================================
    # FILTRE PAR UTILISATEUR
    # ========================================================

    if utilisateur_selectionne.isdigit():
        actions = actions.filter(
            utilisateur_id=int(
                utilisateur_selectionne
            )
        )

    # ========================================================
    # FILTRE PAR PÉRIODE
    # ========================================================

    if nom_champ_date:
        try:
            champ_date_objet = (
                HistoriqueAction
                ._meta
                .get_field(nom_champ_date)
            )
        except Exception:
            champ_date_objet = None

        est_datetime = isinstance(
            champ_date_objet,
            models.DateTimeField,
        )

        if date_debut:
            if est_datetime:
                actions = actions.filter(
                    **{
                        f"{nom_champ_date}__date__gte":
                        date_debut
                    }
                )
            else:
                actions = actions.filter(
                    **{
                        f"{nom_champ_date}__gte":
                        date_debut
                    }
                )

        if date_fin:
            if est_datetime:
                actions = actions.filter(
                    **{
                        f"{nom_champ_date}__date__lte":
                        date_fin
                    }
                )
            else:
                actions = actions.filter(
                    **{
                        f"{nom_champ_date}__lte":
                        date_fin
                    }
                )

    # ========================================================
    # LISTES POUR LES FILTRES
    # ========================================================

    choix_types = obtenir_choix_types()

    entites = list(
        HistoriqueAction.objects
        .exclude(entite="")
        .values_list(
            "entite",
            flat=True,
        )
        .distinct()
        .order_by("entite")
    )

    ids_utilisateurs = list(
        HistoriqueAction.objects
        .exclude(utilisateur_id=None)
        .values_list(
            "utilisateur_id",
            flat=True,
        )
        .distinct()
    )

    utilisateurs = (
        Utilisateur.objects
        .filter(pk__in=ids_utilisateurs)
        .order_by(
            "last_name",
            "first_name",
            "username",
        )
    )

    # ========================================================
    # STATISTIQUES
    # ========================================================

    nombre_total = (
        HistoriqueAction.objects.count()
    )

    nombre_resultats = actions.count()

    nombre_utilisateurs = len(
        ids_utilisateurs
    )

    nombre_entites = len(entites)

    nombre_aujourdhui = None

    if nom_champ_date:
        aujourd_hui = timezone.localdate()

        try:
            champ_date_objet = (
                HistoriqueAction
                ._meta
                .get_field(nom_champ_date)
            )
        except Exception:
            champ_date_objet = None

        if isinstance(
            champ_date_objet,
            models.DateTimeField,
        ):
            nombre_aujourdhui = (
                HistoriqueAction.objects
                .filter(
                    **{
                        f"{nom_champ_date}__date":
                        aujourd_hui
                    }
                )
                .count()
            )
        else:
            nombre_aujourdhui = (
                HistoriqueAction.objects
                .filter(
                    **{
                        nom_champ_date:
                        aujourd_hui
                    }
                )
                .count()
            )

    # ========================================================
    # PAGINATION
    # ========================================================

    paginator = Paginator(
        actions,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    actions_vue = []

    for action in page_obj.object_list:
        date_action = (
            getattr(
                action,
                nom_champ_date,
                None,
            )
            if nom_champ_date
            else None
        )

        adresse_ip = (
            getattr(
                action,
                nom_champ_ip,
                None,
            )
            if nom_champ_ip
            else None
        )

        actions_vue.append(
            {
                "id": action.pk,
                "utilisateur": (
                    action.utilisateur
                ),
                "type_action": (
                    action.type_action
                ),
                "type_label": (
                    obtenir_libelle_type(action)
                ),
                "entite": action.entite,
                "identifiant": (
                    action.identifiant_entite
                ),
                "description": (
                    action.description
                ),
                "date": date_action,
                "adresse_ip": adresse_ip,
                "anciennes_valeurs": (
                    normaliser_valeurs(
                        getattr(
                            action,
                            "anciennes_valeurs",
                            None,
                        )
                    )
                ),
                "nouvelles_valeurs": (
                    normaliser_valeurs(
                        getattr(
                            action,
                            "nouvelles_valeurs",
                            None,
                        )
                    )
                ),
            }
        )

    # ========================================================
    # CONSERVATION DES FILTRES POUR LA PAGINATION
    # ========================================================

    parametres = request.GET.copy()

    if "page" in parametres:
        parametres.pop("page")

    chaine_filtres = parametres.urlencode()

    contexte = {
        "actions": actions_vue,
        "page_obj": page_obj,

        "nombre_total": nombre_total,
        "nombre_resultats": (
            nombre_resultats
        ),
        "nombre_aujourdhui": (
            nombre_aujourdhui
        ),
        "nombre_utilisateurs": (
            nombre_utilisateurs
        ),
        "nombre_entites": nombre_entites,

        "recherche": recherche,
        "type_selectionne": (
            type_selectionne
        ),
        "entite_selectionnee": (
            entite_selectionnee
        ),
        "utilisateur_selectionne": (
            utilisateur_selectionne
        ),
        "date_debut": date_debut,
        "date_fin": date_fin,

        "choix_types": choix_types,
        "entites": entites,
        "utilisateurs": utilisateurs,

        "champ_date_disponible": bool(
            nom_champ_date
        ),
        "chaine_filtres": chaine_filtres,
    }

    return render(
        request,
        "audit/historique_actions.html",
        contexte,
    )
