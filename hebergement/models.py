from pathlib import Path
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MinValueValidator,
)
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
def valider_taille_justificatif(fichier):
    """Limite chaque justificatif à 5 Mo."""
    taille_maximale = 5 * 1024 * 1024

    if fichier.size > taille_maximale:
        raise ValidationError(
            "La taille du fichier ne doit pas dépasser 5 Mo."
        )

class AnneeUniversitaire(models.Model):
    class Statut(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiée"
        ACTIVE = "ACTIVE", "Active"
        CLOTUREE = "CLOTUREE", "Clôturée"

    libelle = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Libellé",
        help_text="Exemple : 2026-2027",
    )

    date_debut = models.DateField(
        verbose_name="Date de début",
    )

    date_fin = models.DateField(
        verbose_name="Date de fin",
    )

    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.PLANIFIEE,
        verbose_name="Statut",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    class Meta:
        verbose_name = "Année universitaire"
        verbose_name_plural = "Années universitaires"
        ordering = [
            "-date_debut",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    date_fin__gt=models.F(
                        "date_debut"
                    )
                ),
                name=(
                    "annee_date_fin_apres_"
                    "date_debut"
                ),
            ),
            models.UniqueConstraint(
                fields=[
                    "statut",
                ],
                condition=Q(
                    statut="ACTIVE"
                ),
                name="une_seule_annee_active",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        # ====================================================
        # NORMALISATION DU LIBELLÉ
        # ====================================================

        if self.libelle:
            self.libelle = self.libelle.strip()

        if not self.libelle:
            erreurs["libelle"] = (
                "Le libellé de l’année universitaire "
                "est obligatoire."
            )

        # ====================================================
        # COHÉRENCE DES DATES
        # ====================================================

        if self.date_debut and self.date_fin:
            if self.date_fin <= self.date_debut:
                erreurs["date_fin"] = (
                    "La date de fin doit être "
                    "postérieure à la date de début."
                )

        # ====================================================
        # CHEVAUCHEMENT DES PÉRIODES
        # ====================================================

        if (
            self.date_debut
            and self.date_fin
            and self.date_fin > self.date_debut
        ):
            annees_chevauchantes = (
                AnneeUniversitaire.objects
                .filter(
                    date_debut__lte=self.date_fin,
                    date_fin__gte=self.date_debut,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if annees_chevauchantes.exists():
                autre_annee = (
                    annees_chevauchantes
                    .order_by(
                        "date_debut"
                    )
                    .first()
                )

                erreurs["date_debut"] = (
                    "Cette période chevauche l’année "
                    f"universitaire {autre_annee.libelle}."
                )

                erreurs["date_fin"] = (
                    "Les périodes des années "
                    "universitaires ne doivent pas "
                    "se chevaucher."
                )

        # ====================================================
        # UNE SEULE ANNÉE ACTIVE
        # ====================================================

        if self.statut == self.Statut.ACTIVE:
            autre_annee_active = (
                AnneeUniversitaire.objects
                .filter(
                    statut=self.Statut.ACTIVE,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if autre_annee_active.exists():
                annee_active = (
                    autre_annee_active.first()
                )

                erreurs["statut"] = (
                    "L’année universitaire "
                    f"{annee_active.libelle} "
                    "est déjà active."
                )

        # ====================================================
        # PROTECTION D’UNE ANNÉE CLÔTURÉE
        # ====================================================

        if self.pk:
            ancienne_version = (
                AnneeUniversitaire.objects
                .filter(
                    pk=self.pk,
                )
                .first()
            )

            if (
                ancienne_version
                and ancienne_version.statut
                == self.Statut.CLOTUREE
            ):
                modifications_interdites = (
                    self.libelle
                    != ancienne_version.libelle
                    or self.date_debut
                    != ancienne_version.date_debut
                    or self.date_fin
                    != ancienne_version.date_fin
                    or self.statut
                    != ancienne_version.statut
                )

                if modifications_interdites:
                    erreurs["__all__"] = (
                        "Une année universitaire clôturée "
                        "ne peut plus être modifiée."
                    )

        # ====================================================
        # PROTECTION DES AFFECTATIONS EXISTANTES
        # ====================================================

        if (
            self.pk
            and self.date_debut
            and self.date_fin
        ):
            affectations = (
        self.affectations.all()
    )

            if affectations.filter(
                date_entree_prevue__lt=(
                    self.date_debut
                ),
            ).exists():
                erreurs["date_debut"] = (
                    "Cette date est postérieure à la "
                    "date d’entrée prévue d’une "
                    "affectation existante."
                )

            if affectations.filter(
                date_sortie_prevue__gt=(
                    self.date_fin
                ),
            ).exists():
                erreurs["date_fin"] = (
                    "Cette date est antérieure à la "
                    "date de sortie prévue d’une "
                    "affectation existante."
                )

        if erreurs:
            raise ValidationError(
                erreurs
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )

    def __str__(self):
        return self.libelle


class Batiment(models.Model):
    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        INACTIF = "INACTIF", "Inactif"
        MAINTENANCE = "MAINTENANCE", "En maintenance"

    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Code",
    )

    nom = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom",
    )

    nombre_etages = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
        ],
        verbose_name="Nombre d'étages",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )

    statut = models.CharField(
        max_length=12,
        choices=Statut.choices,
        default=Statut.ACTIF,
        verbose_name="Statut",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    class Meta:
        verbose_name = "Bâtiment"
        verbose_name_plural = "Bâtiments"

        ordering = [
            "code",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    nombre_etages__gte=1,
                ),
                name="batiment_nombre_etages_positif",
            ),
        ]

    # ========================================================
    # VALIDATION
    # ========================================================

    def clean(self):
        super().clean()

        erreurs = {}

        # ====================================================
        # NORMALISATION DU CODE
        # ====================================================

        if self.code:
            self.code = (
                self.code
                .strip()
                .upper()
            )

        if not self.code:
            erreurs["code"] = (
                "Le code du bâtiment est obligatoire."
            )

        # ====================================================
        # NORMALISATION DU NOM
        # ====================================================

        if self.nom:
            self.nom = self.nom.strip()

        if not self.nom:
            erreurs["nom"] = (
                "Le nom du bâtiment est obligatoire."
            )

        # ====================================================
        # CODE UNIQUE SANS TENIR COMPTE DE LA CASSE
        # ====================================================

        if self.code:
            batiments_meme_code = (
                Batiment.objects
                .filter(
                    code__iexact=self.code,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if batiments_meme_code.exists():
                erreurs["code"] = (
                    "Un bâtiment portant ce code existe déjà."
                )

        # ====================================================
        # NOM UNIQUE SANS TENIR COMPTE DE LA CASSE
        # ====================================================

        if self.nom:
            batiments_meme_nom = (
                Batiment.objects
                .filter(
                    nom__iexact=self.nom,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if batiments_meme_nom.exists():
                erreurs["nom"] = (
                    "Un bâtiment portant ce nom existe déjà."
                )

        # ====================================================
        # NOMBRE D’ÉTAGES
        # ====================================================

        if (
            self.nombre_etages is not None
            and self.nombre_etages < 1
        ):
            erreurs["nombre_etages"] = (
                "Le bâtiment doit contenir au moins un étage."
            )

        # ====================================================
        # CONTRÔLES PENDANT UNE MODIFICATION
        # ====================================================

        if self.pk:
            ancienne_version = (
                Batiment.objects
                .filter(
                    pk=self.pk,
                )
                .first()
            )

            if ancienne_version:
                # ============================================
                # RÉDUCTION DU NOMBRE D’ÉTAGES
                # ============================================

                if (
                    self.nombre_etages is not None
                    and self.nombre_etages
                    < ancienne_version.nombre_etages
                ):
                    chambre_etage_superieur = (
                        self.chambres
                        .filter(
                            etage__gt=self.nombre_etages,
                        )
                        .order_by(
                            "-etage",
                            "numero",
                        )
                        .first()
                    )

                    if chambre_etage_superieur:
                        erreurs["nombre_etages"] = (
                            "Impossible de réduire le bâtiment "
                            f"à {self.nombre_etages} étage(s). "
                            "La chambre "
                            f"{chambre_etage_superieur.numero} "
                            "se trouve actuellement à l’étage "
                            f"{chambre_etage_superieur.etage}."
                        )

                # ============================================
                # DÉSACTIVATION OU MAINTENANCE
                # ============================================

                changement_vers_indisponible = (
                    ancienne_version.statut
                    != self.statut
                    and self.statut
                    in {
                        self.Statut.INACTIF,
                        self.Statut.MAINTENANCE,
                    }
                )

                if changement_vers_indisponible:
                    nombre_affectations_ouvertes = sum(
    chambre.affectations.filter(
        statut__in={
            "PREVUE",
            "ACTIVE",
        },
    ).count()
    for chambre in self.chambres.all()
)

                    if nombre_affectations_ouvertes > 0:
                        erreurs["statut"] = (
                            "Ce bâtiment contient encore "
                            f"{nombre_affectations_ouvertes} "
                            "affectation(s) prévue(s) ou active(s). "
                            "Transférez, annulez ou clôturez ces "
                            "affectations avant de modifier son statut."
                        )

        if erreurs:
            raise ValidationError(
                erreurs
            )

    # ========================================================
    # ENREGISTREMENT
    # ========================================================

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )

    # ========================================================
    # STATISTIQUES DU BÂTIMENT
    # ========================================================

    @property
    def capacite_totale(self):
        return sum(
            chambre.capacite
            for chambre in self.chambres.filter(
                est_active=True,
            )
        )

    @property
    def nombre_places_occupees(self):
        return sum(
            chambre.nombre_places_occupees
            for chambre in self.chambres.filter(
                est_active=True,
            )
        )

    @property
    def nombre_places_disponibles(self):
        return sum(
            chambre.nombre_places_disponibles
            for chambre in self.chambres.filter(
                est_active=True,
            )
        )

    @property
    def taux_occupation(self):
        capacite = self.capacite_totale

        if capacite == 0:
            return 0

        return round(
            (
                self.nombre_places_occupees
                / capacite
            )
            * 100,
            2,
        )

    @property
    def nombre_chambres(self):
        return self.chambres.count()

    @property
    def nombre_chambres_actives(self):
        return self.chambres.filter(
            est_active=True,
        ).count()

    @property
    def nombre_chambres_disponibles(self):
        return sum(
            1
            for chambre in self.chambres.filter(
                est_active=True,
            )
            if (
                chambre.est_disponible_pour_affectation
                and chambre.nombre_places_disponibles > 0
            )
        )

    def __str__(self):
        return f"{self.code} — {self.nom}"


class Chambre(models.Model):
    class TypeChambre(models.TextChoices):
        INDIVIDUELLE = (
            "INDIVIDUELLE",
            "Individuelle",
        )
        DOUBLE = (
            "DOUBLE",
            "Double",
        )
        TRIPLE = (
            "TRIPLE",
            "Triple",
        )
        QUADRUPLE = (
            "QUADRUPLE",
            "Quadruple",
        )
        AUTRE = (
            "AUTRE",
            "Autre",
        )

    class Etat(models.TextChoices):
        DISPONIBLE = (
            "DISPONIBLE",
            "Disponible",
        )
        PARTIELLE = (
            "PARTIELLE",
            "Partiellement occupée",
        )
        COMPLETE = (
            "COMPLETE",
            "Complète",
        )
        MAINTENANCE = (
            "MAINTENANCE",
            "En maintenance",
        )
        HORS_SERVICE = (
            "HORS_SERVICE",
            "Hors service",
        )

    batiment = models.ForeignKey(
        Batiment,
        on_delete=models.PROTECT,
        related_name="chambres",
        verbose_name="Bâtiment",
    )

    numero = models.CharField(
        max_length=20,
        verbose_name="Numéro de chambre",
    )

    etage = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
        ],
        verbose_name="Étage",
    )

    capacite = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
        ],
        verbose_name="Capacité",
    )

    type_chambre = models.CharField(
        max_length=15,
        choices=TypeChambre.choices,
        default=TypeChambre.DOUBLE,
        verbose_name="Type de chambre",
    )

    etat = models.CharField(
        max_length=15,
        choices=Etat.choices,
        default=Etat.DISPONIBLE,
        verbose_name="État",
    )

    est_active = models.BooleanField(
        default=True,
        verbose_name="Chambre active",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    class Meta:
        verbose_name = "Chambre"
        verbose_name_plural = "Chambres"

        ordering = [
            "batiment__code",
            "etage",
            "numero",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "batiment",
                    "numero",
                ],
                name=(
                    "numero_chambre_unique_"
                    "par_batiment"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    capacite__gte=1,
                ),
                name="chambre_capacite_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    etage__gte=0,
                ),
                name="chambre_etage_non_negatif",
            ),
        ]

    # ========================================================
    # VALIDATION
    # ========================================================

    def clean(self):
        super().clean()

        erreurs = {}

        # ====================================================
        # NORMALISATION DU NUMÉRO
        # ====================================================

        if self.numero:
            self.numero = (
                self.numero
                .strip()
                .upper()
            )

        if not self.numero:
            erreurs["numero"] = (
                "Le numéro de la chambre est obligatoire."
            )

        # ====================================================
        # NUMÉRO UNIQUE DANS LE BÂTIMENT
        # ====================================================

        if self.batiment_id and self.numero:
            chambre_existante = (
                Chambre.objects
                .filter(
                    batiment_id=self.batiment_id,
                    numero__iexact=self.numero,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if chambre_existante.exists():
                erreurs["numero"] = (
                    "Une chambre portant ce numéro existe "
                    "déjà dans le bâtiment sélectionné."
                )

        # ====================================================
        # VALIDATION DE L’ÉTAGE
        # ====================================================

        if self.etage is not None and self.etage < 0:
            erreurs["etage"] = (
                "L’étage ne peut pas être négatif."
            )

        if (
            self.batiment_id
            and self.etage is not None
            and self.etage
            > self.batiment.nombre_etages
        ):
            erreurs["etage"] = (
                "L’étage de la chambre ne peut pas "
                "dépasser le nombre d’étages du "
                f"bâtiment ({self.batiment.nombre_etages})."
            )

        # ====================================================
        # VALIDATION DE LA CAPACITÉ
        # ====================================================

        if (
            self.capacite is not None
            and self.capacite < 1
        ):
            erreurs["capacite"] = (
                "La capacité doit être au moins égale à 1."
            )

        nombre_occupants = 0
        nombre_affectations_ouvertes = 0

        if self.pk:
            nombre_occupants = (
                self.affectations
                .filter(
                    statut="ACTIVE",
                )
                .count()
            )

            nombre_affectations_ouvertes = (
                self.affectations
                .filter(
                    statut__in={
                        "PREVUE",
                        "ACTIVE",
                    },
                )
                .count()
            )

        if (
            self.capacite is not None
            and self.capacite < nombre_occupants
        ):
            erreurs["capacite"] = (
                "La capacité ne peut pas être inférieure "
                f"au nombre actuel d’occupants "
                f"({nombre_occupants})."
            )

        # ====================================================
        # ÉTAT DU BÂTIMENT
        # ====================================================

        if (
            self.batiment_id
            and self.est_active
            and self.batiment.statut
            != Batiment.Statut.ACTIF
        ):
            erreurs["est_active"] = (
                "Une chambre ne peut pas être active "
                "dans un bâtiment inactif ou en maintenance."
            )

        # ====================================================
        # MAINTENANCE OU HORS SERVICE
        # ====================================================

        if (
            self.etat
            in {
                self.Etat.MAINTENANCE,
                self.Etat.HORS_SERVICE,
            }
            and nombre_affectations_ouvertes > 0
        ):
            erreurs["etat"] = (
                "Cette chambre contient encore "
                f"{nombre_affectations_ouvertes} "
                "affectation(s) prévue(s) ou active(s). "
                "Transférez, annulez ou clôturez ces "
                "affectations avant de la rendre indisponible."
            )

        # ====================================================
        # DÉSACTIVATION
        # ====================================================

        if (
            not self.est_active
            and nombre_affectations_ouvertes > 0
        ):
            erreurs["est_active"] = (
                "Une chambre contenant des affectations "
                "prévues ou actives ne peut pas être "
                "désactivée."
            )

        if (
            not self.est_active
            and self.etat
            not in {
                self.Etat.MAINTENANCE,
                self.Etat.HORS_SERVICE,
            }
        ):
            erreurs["etat"] = (
                "Une chambre inactive doit être placée "
                "en maintenance ou hors service."
            )

        # ====================================================
        # COHÉRENCE DE L’ÉTAT D’OCCUPATION
        # ====================================================

        if (
            self.etat == self.Etat.COMPLETE
            and self.capacite is not None
            and nombre_occupants < self.capacite
        ):
            erreurs["etat"] = (
                "La chambre ne peut pas être déclarée "
                "complète tant que toutes les places "
                "ne sont pas occupées."
            )

        if (
            self.etat == self.Etat.PARTIELLE
            and (
                nombre_occupants == 0
                or (
                    self.capacite is not None
                    and nombre_occupants >= self.capacite
                )
            )
        ):
            erreurs["etat"] = (
                "L’état « Partiellement occupée » exige "
                "au moins un occupant et au moins une "
                "place encore disponible."
            )

        if (
            self.etat == self.Etat.DISPONIBLE
            and nombre_occupants > 0
        ):
            erreurs["etat"] = (
                "Une chambre contenant des occupants "
                "doit être partiellement occupée ou complète."
            )

        if erreurs:
            raise ValidationError(
                erreurs
            )

    # ========================================================
    # ENREGISTREMENT
    # ========================================================

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )

    # ========================================================
    # OCCUPATION
    # ========================================================

    @property
    def nombre_places_occupees(self):
        if not self.pk:
            return 0

        return (
            self.affectations
            .filter(
                statut="ACTIVE",
            )
            .count()
        )

    @property
    def nombre_places_reservees(self):
        if not self.pk:
            return 0

        return (
            self.affectations
            .filter(
                statut__in={
                    "PREVUE",
                    "ACTIVE",
                },
            )
            .count()
        )

    @property
    def nombre_places_disponibles(self):
        if not self.est_disponible_pour_affectation:
            return 0

        return max(
            self.capacite
            - self.nombre_places_reservees,
            0,
        )

    @property
    def taux_occupation(self):
        if self.capacite <= 0:
            return 0

        return round(
            (
                self.nombre_places_occupees
                / self.capacite
            )
            * 100,
            2,
        )

    @property
    def est_disponible_pour_affectation(self):
        if not self.batiment_id:
            return False

        return (
            self.est_active
            and self.batiment.statut
            == Batiment.Statut.ACTIF
            and self.etat
            not in {
                self.Etat.MAINTENANCE,
                self.Etat.HORS_SERVICE,
                self.Etat.COMPLETE,
            }
            and self.nombre_places_reservees
            < self.capacite
        )

    # ========================================================
    # MISE À JOUR AUTOMATIQUE DE L’ÉTAT
    # ========================================================

    def mettre_a_jour_etat_occupation(self):
        if not self.pk:
            return

        if self.etat in {
            self.Etat.MAINTENANCE,
            self.Etat.HORS_SERVICE,
        }:
            return

        places_occupees = (
            self.nombre_places_occupees
        )

        if places_occupees == 0:
            nouvel_etat = (
                self.Etat.DISPONIBLE
            )

        elif places_occupees >= self.capacite:
            nouvel_etat = (
                self.Etat.COMPLETE
            )

        else:
            nouvel_etat = (
                self.Etat.PARTIELLE
            )

        if self.etat != nouvel_etat:
            Chambre.objects.filter(
                pk=self.pk,
            ).update(
                etat=nouvel_etat,
                date_modification=timezone.now(),
            )

            self.etat = nouvel_etat

    def __str__(self):
        return (
            f"{self.batiment.code} — "
            f"Chambre {self.numero}"
        )
    
class DemandeHebergement(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        SOUMISE = "SOUMISE", "Soumise"
        EN_ETUDE = "EN_ETUDE", "En cours d'étude"
        INCOMPLETE = "INCOMPLETE", "Incomplète"
        ACCEPTEE = "ACCEPTEE", "Acceptée"
        REFUSEE = "REFUSEE", "Refusée"
        LISTE_ATTENTE = "ATTENTE", "Liste d'attente"
        ANNULEE = "ANNULEE", "Annulée"

    etudiant = models.ForeignKey(
    "etudiants.Etudiant",
    on_delete=models.PROTECT,
    related_name="demandes_hebergement",
    verbose_name="Étudiant",
)

    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire,
        on_delete=models.PROTECT,
        related_name="demandes_hebergement",
        verbose_name="Année universitaire",
    )

    motif = models.TextField(
        verbose_name="Motif de la demande",
    )

    distance_domicile = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Distance du domicile en kilomètres",
    )

    situation_sociale = models.TextField(
        blank=True,
        verbose_name="Situation sociale",
    )

    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire complémentaire",
    )

    statut = models.CharField(
        max_length=12,
        choices=Statut.choices,
        default=Statut.BROUILLON,
        verbose_name="Statut",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    date_soumission = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de soumission",
    )

    date_decision = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de décision",
    )

    motif_decision = models.TextField(
        blank=True,
        verbose_name="Motif ou observation de la décision",
    )

    traitee_par = models.ForeignKey(
        "accounts.Utilisateur",
        on_delete=models.SET_NULL,
        related_name="demandes_traitees",
        blank=True,
        null=True,
        limit_choices_to={
            "role__in": ["ADMIN", "RESP"],
        },
        verbose_name="Traitée par",
    )

    class Meta:
        verbose_name = "Demande d'hébergement"
        verbose_name_plural = "Demandes d'hébergement"
        ordering = ["-date_creation"]

        indexes = [
            models.Index(
                fields=["statut"],
                name="demande_statut_idx",
            ),
            models.Index(
                fields=["annee_universitaire", "statut"],
                name="demande_annee_statut_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.annee_universitaire_id
            and self.annee_universitaire.statut
            == AnneeUniversitaire.Statut.CLOTUREE
        ):
            raise ValidationError(
                {
                    "annee_universitaire": (
                        "Une demande ne peut pas être créée pour "
                        "une année universitaire clôturée."
                    )
                }
            )

        if (
    self.etudiant_id
    and self.etudiant.statut != "ACTIF"
    ):
            raise ValidationError(
                {
                    "etudiant": (
                        "Seul un étudiant actif peut déposer "
                        "une demande d'hébergement."
                    )
                }
            )

        statuts_actifs = [
            self.Statut.BROUILLON,
            self.Statut.SOUMISE,
            self.Statut.EN_ETUDE,
            self.Statut.INCOMPLETE,
            self.Statut.ACCEPTEE,
            self.Statut.LISTE_ATTENTE,
        ]

        if (
            self.etudiant_id
            and self.annee_universitaire_id
            and self.statut in statuts_actifs
        ):
            demande_existante = (
                DemandeHebergement.objects
                .filter(
                    etudiant=self.etudiant,
                    annee_universitaire=self.annee_universitaire,
                    statut__in=statuts_actifs,
                )
                .exclude(pk=self.pk)
            )

            if demande_existante.exists():
                raise ValidationError(
                    "Cet étudiant possède déjà une demande active "
                    "pour cette année universitaire."
                )

        if (
            self.statut == self.Statut.REFUSEE
            and not self.motif_decision.strip()
        ):
            raise ValidationError(
                {
                    "motif_decision": (
                        "Le motif de refus est obligatoire."
                    )
                }
            )

        if (
            self.statut == self.Statut.INCOMPLETE
            and not self.motif_decision.strip()
        ):
            raise ValidationError(
                {
                    "motif_decision": (
                        "Indiquez les informations ou les documents "
                        "manquants."
                    )
                }
            )

    @property
    def est_modifiable_par_etudiant(self):
        return self.statut in {
            self.Statut.BROUILLON,
            self.Statut.INCOMPLETE,
        }

    @property
    def peut_etre_affectee(self):
        return self.statut == self.Statut.ACCEPTEE

    def __str__(self):
        return (
            f"Demande de {self.etudiant.matricule} — "
            f"{self.annee_universitaire.libelle}"
        )
    
class Justificatif(models.Model):
    class TypeDocument(models.TextChoices):
        CIN = (
            "CIN",
            "Carte nationale d'identité",
        )

        CERTIFICAT_INSCRIPTION = (
            "CERT_INS",
            "Certificat d'inscription",
        )

        JUSTIFICATIF_DOMICILE = (
            "DOMICILE",
            "Justificatif de domicile",
        )

        JUSTIFICATIF_SOCIAL = (
            "SOCIAL",
            "Justificatif de situation sociale",
        )

        PHOTO = (
            "PHOTO",
            "Photo d'identité",
        )

        AUTRE = (
            "AUTRE",
            "Autre document",
        )

    class StatutValidation(models.TextChoices):
        EN_ATTENTE = (
            "ATTENTE",
            "En attente",
        )

        VALIDE = (
            "VALIDE",
            "Validé",
        )

        REJETE = (
            "REJETE",
            "Rejeté",
        )

    # Documents indispensables pour accepter une demande.
    TYPES_OBLIGATOIRES = {
        TypeDocument.CIN,
        TypeDocument.CERTIFICAT_INSCRIPTION,
        TypeDocument.JUSTIFICATIF_DOMICILE,
        TypeDocument.JUSTIFICATIF_SOCIAL,
        TypeDocument.PHOTO,
    }

    demande = models.ForeignKey(
        DemandeHebergement,
        on_delete=models.CASCADE,
        related_name="justificatifs",
        verbose_name="Demande d'hébergement",
    )

    type_document = models.CharField(
        max_length=15,
        choices=TypeDocument.choices,
        verbose_name="Type de document",
    )

    fichier = models.FileField(
        upload_to=(
            "hebergement/justificatifs/%Y/%m/"
        ),
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "jpg",
                    "jpeg",
                    "png",
                ]
            ),
            valider_taille_justificatif,
        ],
        verbose_name="Fichier",
    )

    nom_original = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nom original du fichier",
    )

    statut_validation = models.CharField(
        max_length=10,
        choices=StatutValidation.choices,
        default=StatutValidation.EN_ATTENTE,
        verbose_name="Statut de validation",
    )

    commentaire_validation = models.TextField(
        blank=True,
        verbose_name="Commentaire de validation",
    )

    date_ajout = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'ajout",
    )

    date_validation = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de validation",
    )

    class Meta:
        verbose_name = "Justificatif"
        verbose_name_plural = "Justificatifs"

        ordering = [
            "type_document",
            "-date_ajout",
        ]

        constraints = [
            # Un seul document obligatoire de chaque type
            # par demande. Plusieurs documents AUTRE restent permis.
            models.UniqueConstraint(
                fields=[
                    "demande",
                    "type_document",
                ],
                condition=~models.Q(
                    type_document="AUTRE",
                ),
                name=(
                    "justificatif_unique_par_type_demande"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "demande",
                    "statut_validation",
                ],
                name="justif_demande_statut_idx",
            ),
            models.Index(
                fields=[
                    "type_document",
                ],
                name="justif_type_idx",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        self.commentaire_validation = (
            self.commentaire_validation or ""
        ).strip()

        # ====================================================
        # COHÉRENCE DU STATUT DE VALIDATION
        # ====================================================

        if (
            self.statut_validation
            == self.StatutValidation.REJETE
            and not self.commentaire_validation
        ):
            erreurs["commentaire_validation"] = (
                "Le motif du rejet du document est obligatoire."
            )

        if (
            self.statut_validation
            == self.StatutValidation.EN_ATTENTE
        ):
            if self.date_validation:
                erreurs["date_validation"] = (
                    "Un justificatif en attente ne peut pas "
                    "posséder de date de validation."
                )

        else:
            if not self.date_validation:
                erreurs["date_validation"] = (
                    "Une date de validation est obligatoire "
                    "pour un justificatif validé ou rejeté."
                )

        # ====================================================
        # DEMANDE MODIFIABLE
        # ====================================================

        if self.demande_id:
            statuts_non_modifiables = {
                DemandeHebergement.Statut.ACCEPTEE,
                DemandeHebergement.Statut.REFUSEE,
            }

            if (
                not self.pk
                and self.demande.statut
                in statuts_non_modifiables
            ):
                erreurs["demande"] = (
                    "Il n'est pas possible d'ajouter un "
                    "justificatif à une demande déjà traitée."
                )

        # ====================================================
        # UNICITÉ DU TYPE OBLIGATOIRE
        # ====================================================

        if (
            self.demande_id
            and self.type_document
            and self.type_document
            != self.TypeDocument.AUTRE
        ):
            doublon = (
                Justificatif.objects
                .filter(
                    demande_id=self.demande_id,
                    type_document=self.type_document,
                )
                .exclude(
                    pk=self.pk,
                )
                .exists()
            )

            if doublon:
                erreurs["type_document"] = (
                    "Un justificatif de ce type existe déjà "
                    "pour cette demande."
                )

        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        if self.fichier:
            nom_fichier = Path(
                self.fichier.name
            ).name

            if (
                not self.nom_original
                or self._state.adding
            ):
                self.nom_original = (
                    nom_fichier[:255]
                )

        # Ajustement automatique de la date selon le statut.
        if (
            self.statut_validation
            == self.StatutValidation.EN_ATTENTE
        ):
            self.date_validation = None

        elif not self.date_validation:
            self.date_validation = timezone.now()

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    def valider(self, commentaire=""):
        if (
            self.statut_validation
            != self.StatutValidation.EN_ATTENTE
        ):
            raise ValidationError(
                "Seul un justificatif en attente peut être validé."
            )

        self.statut_validation = (
            self.StatutValidation.VALIDE
        )

        self.commentaire_validation = (
            commentaire or ""
        ).strip()

        self.date_validation = timezone.now()

        self.save(
            update_fields=[
                "statut_validation",
                "commentaire_validation",
                "date_validation",
            ]
        )

    def rejeter(self, commentaire):
        commentaire = (
            commentaire or ""
        ).strip()

        if not commentaire:
            raise ValidationError(
                {
                    "commentaire_validation": (
                        "Le motif du rejet est obligatoire."
                    )
                }
            )

        if (
            self.statut_validation
            != self.StatutValidation.EN_ATTENTE
        ):
            raise ValidationError(
                "Seul un justificatif en attente peut être rejeté."
            )

        self.statut_validation = (
            self.StatutValidation.REJETE
        )

        self.commentaire_validation = commentaire
        self.date_validation = timezone.now()

        self.save(
            update_fields=[
                "statut_validation",
                "commentaire_validation",
                "date_validation",
            ]
        )

    def remettre_en_attente(self):
        self.statut_validation = (
            self.StatutValidation.EN_ATTENTE
        )

        self.commentaire_validation = ""
        self.date_validation = None

        self.save(
            update_fields=[
                "statut_validation",
                "commentaire_validation",
                "date_validation",
            ]
        )

    @property
    def est_valide(self):
        return (
            self.statut_validation
            == self.StatutValidation.VALIDE
        )

    @property
    def est_rejete(self):
        return (
            self.statut_validation
            == self.StatutValidation.REJETE
        )

    def __str__(self):
        return (
            f"{self.get_type_document_display()} — "
            f"{self.demande.etudiant.matricule}"
        )

class Affectation(models.Model):
    class Statut(models.TextChoices):
        PREVUE = "PREVUE", "Prévue"
        ACTIVE = "ACTIVE", "Active"
        CLOTUREE = "CLOTUREE", "Clôturée"
        ANNULEE = "ANNULEE", "Annulée"

    etudiant = models.ForeignKey(
        "etudiants.Etudiant",
        on_delete=models.PROTECT,
        related_name="affectations",
        verbose_name="Étudiant",
    )

    chambre = models.ForeignKey(
        Chambre,
        on_delete=models.PROTECT,
        related_name="affectations",
        verbose_name="Chambre",
    )

    annee_universitaire = models.ForeignKey(
        AnneeUniversitaire,
        on_delete=models.PROTECT,
        related_name="affectations",
        verbose_name="Année universitaire",
    )

    demande_hebergement = models.ForeignKey(
        DemandeHebergement,
        on_delete=models.PROTECT,
        related_name="affectations",
        verbose_name="Demande d'hébergement",
    )

    date_entree_prevue = models.DateField(
        verbose_name="Date d'entrée prévue",
    )

    date_entree_reelle = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date d'entrée réelle",
    )

    date_sortie_prevue = models.DateField(
        verbose_name="Date de sortie prévue",
    )

    date_sortie_reelle = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date de sortie réelle",
    )

    motif_sortie = models.TextField(
        blank=True,
        verbose_name="Motif de sortie",
    )

    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.PREVUE,
        verbose_name="Statut",
    )

    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="affectations_creees",
        blank=True,
        null=True,
        limit_choices_to={
            "role__in": [
                "ADMIN",
                "RESP",
            ],
        },
        verbose_name="Créée par",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    class Meta:
        verbose_name = "Affectation"
        verbose_name_plural = "Affectations"

        ordering = [
            "-date_creation",
        ]

        indexes = [
            models.Index(
                fields=[
                    "statut",
                ],
                name="affectation_statut_idx",
            ),
            models.Index(
                fields=[
                    "chambre",
                    "statut",
                ],
                name="affectation_chambre_idx",
            ),
            models.Index(
                fields=[
                    "etudiant",
                    "statut",
                ],
                name="affectation_etudiant_idx",
            ),
            models.Index(
                fields=[
                    "annee_universitaire",
                    "statut",
                ],
                name="affectation_annee_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    date_sortie_prevue__gte=models.F(
                        "date_entree_prevue"
                    )
                ),
                name="affectation_sortie_prevue_valide",
            ),

            models.UniqueConstraint(
                fields=[
                    "etudiant",
                ],
                condition=Q(
                    statut__in=[
                        "PREVUE",
                        "ACTIVE",
                    ]
                ),
                name=(
                    "une_affectation_ouverte_"
                    "par_etudiant"
                ),
            ),

            models.UniqueConstraint(
                fields=[
                    "demande_hebergement",
                ],
                condition=Q(
                    statut__in=[
                        "PREVUE",
                        "ACTIVE",
                    ]
                ),
                name=(
                    "une_affectation_ouverte_"
                    "par_demande"
                ),
            ),
        ]

    # ========================================================
    # VALIDATION
    # ========================================================

    def clean(self):
        super().clean()

        erreurs = {}

        statuts_ouverts = {
            self.Statut.PREVUE,
            self.Statut.ACTIVE,
        }

        # ====================================================
        # COHÉRENCE DEMANDE / ÉTUDIANT
        # ====================================================

        if (
            self.demande_hebergement_id
            and self.etudiant_id
            and self.demande_hebergement.etudiant_id
            != self.etudiant_id
        ):
            erreurs["demande_hebergement"] = (
                "Cette demande ne correspond pas "
                "à l’étudiant sélectionné."
            )

        # ====================================================
        # COHÉRENCE DEMANDE / ANNÉE UNIVERSITAIRE
        # ====================================================

        if (
            self.demande_hebergement_id
            and self.annee_universitaire_id
            and self.demande_hebergement.annee_universitaire_id
            != self.annee_universitaire_id
        ):
            erreurs["annee_universitaire"] = (
                "L’année universitaire doit correspondre "
                "à celle de la demande d’hébergement."
            )

        # ====================================================
        # DEMANDE ACCEPTÉE
        # ====================================================

        if (
            self.demande_hebergement_id
            and self.demande_hebergement.statut
            != DemandeHebergement.Statut.ACCEPTEE
        ):
            erreurs["demande_hebergement"] = (
                "Une affectation exige une demande "
                "d’hébergement acceptée."
            )

        # ====================================================
        # ÉTUDIANT ACTIF
        # ====================================================

        if (
            self.etudiant_id
            and self.etudiant.statut != "ACTIF"
        ):
            erreurs["etudiant"] = (
                "Un étudiant inactif ne peut pas "
                "être affecté."
            )

        # ====================================================
        # ANNÉE UNIVERSITAIRE NON CLÔTURÉE
        # ====================================================

        if (
            self.annee_universitaire_id
            and self.statut in statuts_ouverts
            and self.annee_universitaire.statut
            == AnneeUniversitaire.Statut.CLOTUREE
        ):
            erreurs["annee_universitaire"] = (
                "Une affectation ouverte ne peut pas être "
                "créée dans une année universitaire clôturée."
            )

        # ====================================================
        # UNE SEULE AFFECTATION OUVERTE PAR ÉTUDIANT
        # ====================================================

        if (
            self.etudiant_id
            and self.statut in statuts_ouverts
        ):
            affectation_ouverte = (
                Affectation.objects
                .filter(
                    etudiant_id=self.etudiant_id,
                    statut__in=statuts_ouverts,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if affectation_ouverte.exists():
                erreurs["etudiant"] = (
                    "Cet étudiant possède déjà une "
                    "affectation prévue ou active."
                )

        # ====================================================
        # UNE SEULE AFFECTATION OUVERTE PAR DEMANDE
        # ====================================================

        if (
            self.demande_hebergement_id
            and self.statut in statuts_ouverts
        ):
            affectation_demande = (
                Affectation.objects
                .filter(
                    demande_hebergement_id=(
                        self.demande_hebergement_id
                    ),
                    statut__in=statuts_ouverts,
                )
                .exclude(
                    pk=self.pk,
                )
            )

            if affectation_demande.exists():
                erreurs["demande_hebergement"] = (
                    "Cette demande possède déjà une "
                    "affectation prévue ou active."
                )

        # ====================================================
        # VÉRIFICATION DE LA CHAMBRE
        # ====================================================

        if (
            self.chambre_id
            and self.statut in statuts_ouverts
        ):
            if not self.chambre.est_active:
                erreurs["chambre"] = (
                    "La chambre sélectionnée est désactivée."
                )

            elif (
                self.chambre.batiment.statut
                != Batiment.Statut.ACTIF
            ):
                erreurs["chambre"] = (
                    "Le bâtiment de cette chambre "
                    "n’est pas actif."
                )

            elif self.chambre.etat in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
            }:
                erreurs["chambre"] = (
                    "Une chambre en maintenance ou hors "
                    "service ne peut recevoir aucune affectation."
                )

            else:
                places_reservees = (
                    Affectation.objects
                    .filter(
                        chambre_id=self.chambre_id,
                        statut__in=statuts_ouverts,
                    )
                    .exclude(
                        pk=self.pk,
                    )
                    .count()
                )

                places_apres_affectation = (
                    places_reservees + 1
                )

                if (
                    places_apres_affectation
                    > self.chambre.capacite
                ):
                    erreurs["chambre"] = (
                        "La capacité maximale de cette "
                        "chambre serait dépassée."
                    )

        # ====================================================
        # DATES PRÉVUES
        # ====================================================

        if (
            self.date_entree_prevue
            and self.date_sortie_prevue
            and self.date_sortie_prevue
            < self.date_entree_prevue
        ):
            erreurs["date_sortie_prevue"] = (
                "La date de sortie prévue ne peut pas "
                "être antérieure à la date d’entrée prévue."
            )

        if (
            self.annee_universitaire_id
            and self.date_entree_prevue
            and self.date_entree_prevue
            < self.annee_universitaire.date_debut
        ):
            erreurs["date_entree_prevue"] = (
                "La date d’entrée prévue ne peut pas être "
                "antérieure au début de l’année universitaire."
            )

        if (
            self.annee_universitaire_id
            and self.date_sortie_prevue
            and self.date_sortie_prevue
            > self.annee_universitaire.date_fin
        ):
            erreurs["date_sortie_prevue"] = (
                "La date de sortie prévue ne peut pas "
                "dépasser la fin de l’année universitaire."
            )

        # ====================================================
        # DATES RÉELLES
        # ====================================================

        if (
            self.date_entree_reelle
            and self.date_sortie_reelle
            and self.date_sortie_reelle
            < self.date_entree_reelle
        ):
            erreurs["date_sortie_reelle"] = (
                "La date de sortie réelle ne peut pas être "
                "antérieure à la date d’entrée réelle."
            )

        if (
            self.date_entree_reelle
            and self.date_entree_prevue
            and self.date_entree_reelle
            < self.date_entree_prevue
        ):
            erreurs["date_entree_reelle"] = (
                "La date d’entrée réelle ne peut pas être "
                "antérieure à la date d’entrée prévue."
            )

        # ====================================================
        # COHÉRENCE DU STATUT
        # ====================================================

        if self.statut == self.Statut.PREVUE:
            if self.date_entree_reelle:
                erreurs["date_entree_reelle"] = (
                    "Une affectation prévue ne doit pas encore "
                    "posséder de date d’entrée réelle."
                )

            if self.date_sortie_reelle:
                erreurs["date_sortie_reelle"] = (
                    "Une affectation prévue ne doit pas "
                    "posséder de date de sortie réelle."
                )

        if self.statut == self.Statut.ACTIVE:
            if not self.date_entree_reelle:
                erreurs["date_entree_reelle"] = (
                    "La date d’entrée réelle est obligatoire "
                    "pour une affectation active."
                )

            if self.date_sortie_reelle:
                erreurs["date_sortie_reelle"] = (
                    "Une affectation active ne peut pas encore "
                    "posséder de date de sortie réelle."
                )

        if self.statut == self.Statut.CLOTUREE:
            if not self.date_entree_reelle:
                erreurs["date_entree_reelle"] = (
                    "Une affectation clôturée doit posséder "
                    "une date d’entrée réelle."
                )

            if not self.date_sortie_reelle:
                erreurs["date_sortie_reelle"] = (
                    "La date de sortie réelle est obligatoire "
                    "pour clôturer l’affectation."
                )

            if not self.motif_sortie.strip():
                erreurs["motif_sortie"] = (
                    "Le motif de sortie est obligatoire "
                    "pour clôturer l’affectation."
                )

        if self.statut == self.Statut.ANNULEE:
            if self.date_entree_reelle:
                erreurs["statut"] = (
                    "Une affectation ayant déjà commencé "
                    "ne peut pas être annulée. Elle doit être "
                    "clôturée."
                )

        if erreurs:
            raise ValidationError(
                erreurs
            )

    # ========================================================
    # ENREGISTREMENT
    # ========================================================

    def save(self, *args, **kwargs):
        ancienne_chambre = None

        if self.pk:
            ancienne_affectation = (
                Affectation.objects
                .filter(
                    pk=self.pk,
                )
                .select_related(
                    "chambre",
                )
                .first()
            )

            if ancienne_affectation:
                ancienne_chambre = (
                    ancienne_affectation.chambre
                )

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

        if (
            ancienne_chambre
            and ancienne_chambre.pk
            != self.chambre_id
        ):
            ancienne_chambre.mettre_a_jour_etat_occupation()

        if self.chambre_id:
            self.chambre.mettre_a_jour_etat_occupation()

    # ========================================================
    # CONFIRMATION D’ENTRÉE
    # ========================================================

    def confirmer_entree(
        self,
        date_entree=None,
    ):
        if self.statut != self.Statut.PREVUE:
            raise ValidationError(
                "Seule une affectation prévue "
                "peut être activée."
            )

        date_entree = (
            date_entree
            or timezone.localdate()
        )

        if (
            self.date_entree_prevue
            and date_entree
            < self.date_entree_prevue
        ):
            raise ValidationError(
                "La date d’entrée réelle ne peut pas être "
                "antérieure à la date d’entrée prévue."
            )

        self.date_entree_reelle = date_entree
        self.date_sortie_reelle = None
        self.motif_sortie = ""
        self.statut = self.Statut.ACTIVE

        self.save()

    # ========================================================
    # CLÔTURE
    # ========================================================

    def cloturer(
        self,
        motif_sortie,
        date_sortie=None,
    ):
        if self.statut != self.Statut.ACTIVE:
            raise ValidationError(
                "Seule une affectation active "
                "peut être clôturée."
            )

        motif_sortie = (
            motif_sortie or ""
        ).strip()

        if not motif_sortie:
            raise ValidationError(
                "Le motif de sortie est obligatoire."
            )

        date_sortie = (
            date_sortie
            or timezone.localdate()
        )

        if (
            self.date_entree_reelle
            and date_sortie
            < self.date_entree_reelle
        ):
            raise ValidationError(
                "La date de sortie réelle ne peut pas être "
                "antérieure à la date d’entrée réelle."
            )

        self.date_sortie_reelle = date_sortie
        self.motif_sortie = motif_sortie
        self.statut = self.Statut.CLOTUREE

        self.save()

    # ========================================================
    # ANNULATION
    # ========================================================

    def annuler(self):
        if self.statut != self.Statut.PREVUE:
            raise ValidationError(
                "Seule une affectation prévue "
                "peut être annulée."
            )

        self.date_entree_reelle = None
        self.date_sortie_reelle = None
        self.motif_sortie = ""
        self.statut = self.Statut.ANNULEE

        self.save()

    @property
    def est_active(self):
        return (
            self.statut
            == self.Statut.ACTIVE
        )

    @property
    def est_ouverte(self):
        return self.statut in {
            self.Statut.PREVUE,
            self.Statut.ACTIVE,
        }

    def __str__(self):
        return (
            f"{self.etudiant.matricule} — "
            f"{self.chambre.batiment.code}/"
            f"{self.chambre.numero}"
        )

class AffectationForm(forms.ModelForm):
    class Meta:
        model = Affectation

        fields = [
            "chambre",
            "date_entree_prevue",
            "date_sortie_prevue",
        ]

        widgets = {
            "chambre": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "date_entree_prevue": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "date_sortie_prevue": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        chambres = (
            Chambre.objects
            .filter(
                est_active=True,
                batiment__statut=Batiment.Statut.ACTIF,
            )
            .exclude(
                etat__in={
                    Chambre.Etat.MAINTENANCE,
                    Chambre.Etat.HORS_SERVICE,
                    Chambre.Etat.COMPLETE,
                }
            )
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

        chambres_disponibles = [
            chambre.pk
            for chambre in chambres
            if chambre.nombre_places_disponibles > 0
        ]

        self.fields["chambre"].queryset = (
            Chambre.objects
            .filter(
                pk__in=chambres_disponibles,
            )
            .select_related(
                "batiment",
            )
            .order_by(
                "batiment__code",
                "etage",
                "numero",
            )
        )

        self.fields["chambre"].empty_label = (
            "Sélectionnez une chambre disponible"
        )

    def clean(self):
        donnees = super().clean()

        chambre = donnees.get(
            "chambre"
        )

        date_entree_prevue = donnees.get(
            "date_entree_prevue"
        )

        date_sortie_prevue = donnees.get(
            "date_sortie_prevue"
        )

        if (
            date_entree_prevue
            and date_sortie_prevue
            and date_sortie_prevue
            < date_entree_prevue
        ):
            self.add_error(
                "date_sortie_prevue",
                (
                    "La date de sortie prévue ne peut pas "
                    "être antérieure à la date d’entrée prévue."
                ),
            )

        if chambre:
            if not chambre.est_active:
                self.add_error(
                    "chambre",
                    "La chambre sélectionnée est désactivée.",
                )

            elif (
                chambre.batiment.statut
                != Batiment.Statut.ACTIF
            ):
                self.add_error(
                    "chambre",
                    (
                        "Le bâtiment de cette chambre "
                        "n’est pas actif."
                    ),
                )

            elif chambre.etat in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
                Chambre.Etat.COMPLETE,
            }:
                self.add_error(
                    "chambre",
                    (
                        "Cette chambre n’est pas disponible "
                        "pour une nouvelle affectation."
                    ),
                )

            elif chambre.nombre_places_disponibles <= 0:
                self.add_error(
                    "chambre",
                    (
                        "Cette chambre ne possède plus "
                        "de place disponible."
                    ),
                )

        return donnees

class Transfert(models.Model):
    ancienne_affectation = models.OneToOneField(
        Affectation,
        on_delete=models.PROTECT,
        related_name="transfert_sortant",
        verbose_name="Ancienne affectation",
    )

    nouvelle_affectation = models.OneToOneField(
        Affectation,
        on_delete=models.PROTECT,
        related_name="transfert_entrant",
        verbose_name="Nouvelle affectation",
    )

    motif = models.TextField(
        verbose_name="Motif du transfert",
    )

    date_transfert = models.DateField(
        default=timezone.localdate,
        verbose_name="Date du transfert",
    )

    effectue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="transferts_effectues",
        blank=True,
        null=True,
        limit_choices_to={
            "role__in": ["ADMIN", "RESP"],
        },
        verbose_name="Effectué par",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    class Meta:
        verbose_name = "Transfert"
        verbose_name_plural = "Transferts"
        ordering = [
            "-date_transfert",
            "-date_creation",
        ]

        constraints = [
            models.CheckConstraint(
                condition=~models.Q(
                    ancienne_affectation=models.F(
                        "nouvelle_affectation"
                    )
                ),
                name=(
                    "transfert_affectations_differentes"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "date_transfert",
                ],
                name="transfert_date_idx",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        if self.motif:
            self.motif = self.motif.strip()

        if not self.motif:
            erreurs["motif"] = (
                "Le motif du transfert est obligatoire."
            )

        if (
            self.ancienne_affectation_id
            and self.nouvelle_affectation_id
        ):
            ancienne = self.ancienne_affectation
            nouvelle = self.nouvelle_affectation

            if (
                self.ancienne_affectation_id
                == self.nouvelle_affectation_id
            ):
                erreurs["nouvelle_affectation"] = (
                    "L’ancienne et la nouvelle affectation "
                    "doivent être différentes."
                )

            if (
                ancienne.etudiant_id
                != nouvelle.etudiant_id
            ):
                erreurs["nouvelle_affectation"] = (
                    "Les deux affectations doivent concerner "
                    "le même étudiant."
                )

            if (
                ancienne.chambre_id
                == nouvelle.chambre_id
            ):
                erreurs["nouvelle_affectation"] = (
                    "La nouvelle chambre doit être différente "
                    "de l’ancienne chambre."
                )

            if (
                ancienne.annee_universitaire_id
                != nouvelle.annee_universitaire_id
            ):
                erreurs["nouvelle_affectation"] = (
                    "Les deux affectations doivent appartenir "
                    "à la même année universitaire."
                )

            if (
                ancienne.demande_hebergement_id
                != nouvelle.demande_hebergement_id
            ):
                erreurs["nouvelle_affectation"] = (
                    "Les deux affectations doivent être liées "
                    "à la même demande d’hébergement."
                )

            if (
                ancienne.statut
                != Affectation.Statut.CLOTUREE
            ):
                erreurs["ancienne_affectation"] = (
                    "L’ancienne affectation doit être clôturée "
                    "avant l’enregistrement du transfert."
                )

            if (
                nouvelle.statut
                != Affectation.Statut.ACTIVE
            ):
                erreurs["nouvelle_affectation"] = (
                    "La nouvelle affectation du transfert "
                    "doit être active."
                )

            if (
                ancienne.date_sortie_reelle
                and self.date_transfert
                and ancienne.date_sortie_reelle
                != self.date_transfert
            ):
                erreurs["date_transfert"] = (
                    "La date du transfert doit correspondre "
                    "à la date de sortie de l’ancienne "
                    "affectation."
                )

            if (
                nouvelle.date_entree_reelle
                and self.date_transfert
                and nouvelle.date_entree_reelle
                != self.date_transfert
            ):
                erreurs["date_transfert"] = (
                    "La date du transfert doit correspondre "
                    "à la date d’entrée de la nouvelle "
                    "affectation."
                )

            if (
                ancienne.date_entree_reelle
                and self.date_transfert
                and self.date_transfert
                < ancienne.date_entree_reelle
            ):
                erreurs["date_transfert"] = (
                    "La date du transfert ne peut pas être "
                    "antérieure à la date d’entrée réelle "
                    "de l’étudiant."
                )

            annee = ancienne.annee_universitaire

            if (
                self.date_transfert
                and (
                    self.date_transfert < annee.date_debut
                    or self.date_transfert > annee.date_fin
                )
            ):
                erreurs["date_transfert"] = (
                    "La date du transfert doit être comprise "
                    "dans la période de l’année universitaire."
                )

        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    def __str__(self):
        return (
            "Transfert de "
            f"{self.ancienne_affectation.etudiant.matricule} : "
            f"{self.ancienne_affectation.chambre.batiment.code}/"
            f"{self.ancienne_affectation.chambre.numero} vers "
            f"{self.nouvelle_affectation.chambre.batiment.code}/"
            f"{self.nouvelle_affectation.chambre.numero}"
        )
    
@transaction.atomic
def transferer_etudiant(
    affectation_active,
    nouvelle_chambre,
    motif,
    utilisateur,
    date_transfert=None,
):
    """
    Transfère un étudiant d'une chambre vers une autre
    dans une seule transaction.
    """

    motif = (motif or "").strip()
    date_operation = (
        date_transfert
        or timezone.localdate()
    )

    if not motif:
        raise ValidationError(
            {
                "motif": (
                    "Le motif du transfert est obligatoire."
                )
            }
        )

    if not affectation_active.pk:
        raise ValidationError(
            "L'affectation à transférer doit être enregistrée."
        )

    if not nouvelle_chambre.pk:
        raise ValidationError(
            "La nouvelle chambre doit être enregistrée."
        )

    # ========================================================
    # VERROUILLER ET RECHARGER L'AFFECTATION
    # ========================================================

    affectation_active = (
        Affectation.objects
        .select_for_update()
        .select_related(
            "etudiant",
            "chambre",
            "chambre__batiment",
            "annee_universitaire",
            "demande_hebergement",
        )
        .get(
            pk=affectation_active.pk,
        )
    )

    if (
        affectation_active.statut
        != Affectation.Statut.ACTIVE
    ):
        raise ValidationError(
            "L'étudiant doit posséder une affectation active."
        )

    if (
        affectation_active.chambre_id
        == nouvelle_chambre.pk
    ):
        raise ValidationError(
            "La nouvelle chambre doit être différente "
            "de la chambre actuelle."
        )

    ancienne_chambre_id = (
        affectation_active.chambre_id
    )

    nouvelle_chambre_id = (
        nouvelle_chambre.pk
    )

    identifiants_chambres = sorted(
        {
            ancienne_chambre_id,
            nouvelle_chambre_id,
        }
    )

    chambres_verrouillees = {
        chambre.pk: chambre
        for chambre in (
            Chambre.objects
            .select_for_update()
            .select_related(
                "batiment",
            )
            .filter(
                pk__in=identifiants_chambres,
            )
            .order_by(
                "pk",
            )
        )
    }

    ancienne_chambre = chambres_verrouillees.get(
        ancienne_chambre_id
    )

    nouvelle_chambre = chambres_verrouillees.get(
        nouvelle_chambre_id
    )

    if not ancienne_chambre or not nouvelle_chambre:
        raise ValidationError(
            "Une des chambres concernées par le transfert "
            "n'existe plus."
        )

    # ========================================================
    # CONTRÔLER ET CORRIGER LES DATES
    # ========================================================

    annee = affectation_active.annee_universitaire
    date_fin_annee = annee.date_fin

    if (
        date_operation < annee.date_debut
        or date_operation > date_fin_annee
    ):
        raise ValidationError(
            {
                "date_transfert": (
                    "La date du transfert doit être comprise "
                    "dans l'année universitaire."
                )
            }
        )

    if (
        affectation_active.date_entree_reelle
        and date_operation
        < affectation_active.date_entree_reelle
    ):
        raise ValidationError(
            {
                "date_transfert": (
                    "La date du transfert ne peut pas être "
                    "antérieure à la date d'entrée réelle."
                )
            }
        )

    # Corriger une ancienne date incohérente avant cloturer().
    if (
        affectation_active.date_sortie_prevue
        and affectation_active.date_sortie_prevue
        > date_fin_annee
    ):
        affectation_active.date_sortie_prevue = (
            date_fin_annee
        )

    if (
        affectation_active.date_sortie_prevue
        and date_operation
        > affectation_active.date_sortie_prevue
    ):
        raise ValidationError(
            {
                "date_transfert": (
                    "La date du transfert ne peut pas dépasser "
                    "la date de sortie prévue."
                )
            }
        )

    # ========================================================
    # CONTRÔLER LA NOUVELLE CHAMBRE
    # ========================================================

    if not nouvelle_chambre.est_active:
        raise ValidationError(
            {
                "nouvelle_chambre": (
                    "La nouvelle chambre est désactivée."
                )
            }
        )

    if (
        nouvelle_chambre.batiment.statut
        != Batiment.Statut.ACTIF
    ):
        raise ValidationError(
            {
                "nouvelle_chambre": (
                    "Le bâtiment de la nouvelle chambre "
                    "n'est pas actif."
                )
            }
        )

    if nouvelle_chambre.etat in {
        Chambre.Etat.MAINTENANCE,
        Chambre.Etat.HORS_SERVICE,
        Chambre.Etat.COMPLETE,
    }:
        raise ValidationError(
            {
                "nouvelle_chambre": (
                    "La nouvelle chambre n'est pas disponible."
                )
            }
        )

    if (
        nouvelle_chambre.nombre_places_disponibles
        <= 0
    ):
        raise ValidationError(
            {
                "nouvelle_chambre": (
                    "La nouvelle chambre ne possède plus "
                    "de place disponible."
                )
            }
        )

    # ========================================================
    # CLÔTURER L'ANCIENNE AFFECTATION
    # ========================================================

    affectation_active.cloturer(
        motif_sortie=f"Transfert : {motif}",
        date_sortie=date_operation,
    )

    # ========================================================
    # CRÉER LA NOUVELLE AFFECTATION ACTIVE
    # ========================================================

    nouvelle_affectation = Affectation(
        etudiant=affectation_active.etudiant,
        chambre=nouvelle_chambre,
        annee_universitaire=(
            affectation_active.annee_universitaire
        ),
        demande_hebergement=(
            affectation_active.demande_hebergement
        ),
        date_entree_prevue=date_operation,
        date_entree_reelle=date_operation,
        date_sortie_prevue=(
            affectation_active.date_sortie_prevue
        ),
        date_sortie_reelle=None,
        motif_sortie="",
        statut=Affectation.Statut.ACTIVE,
        creee_par=utilisateur,
    )

    nouvelle_affectation.save()

    # ========================================================
    # ENREGISTRER LE TRANSFERT
    # ========================================================

    transfert = Transfert(
        ancienne_affectation=affectation_active,
        nouvelle_affectation=nouvelle_affectation,
        motif=motif,
        date_transfert=date_operation,
        effectue_par=utilisateur,
    )

    transfert.save()

    # ========================================================
    # ACTUALISER LES DEUX CHAMBRES
    # ========================================================

    ancienne_chambre.mettre_a_jour_etat_occupation()
    nouvelle_chambre.mettre_a_jour_etat_occupation()

    return transfert