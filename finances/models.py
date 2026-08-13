from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone




class FraisHebergement(models.Model):
    """
    Représente le montant qu'un étudiant doit payer
    pour une année universitaire.
    """

    etudiant = models.ForeignKey(
    "etudiants.Etudiant",
    on_delete=models.PROTECT,
    related_name="frais_hebergement",
    verbose_name="Étudiant",
)

    annee_universitaire = models.ForeignKey(
    "hebergement.AnneeUniversitaire",
    on_delete=models.PROTECT,
    related_name="frais_hebergement",
    verbose_name="Année universitaire",
)

    montant_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Montant total dû",
    )

    date_echeance = models.DateField(
        verbose_name="Date d'échéance",
    )

    est_actif = models.BooleanField(
        default=True,
        verbose_name="Frais actifs",
    )

    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire",
    )

    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="frais_hebergement_crees",
        blank=True,
        null=True,
        limit_choices_to={
            "role__in": ["ADMIN", "RESP"],
        },
        verbose_name="Créé par",
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
        verbose_name = "Frais d'hébergement"
        verbose_name_plural = "Frais d'hébergement"
        ordering = [
            "-annee_universitaire__date_debut",
            "etudiant__matricule",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "etudiant",
                    "annee_universitaire",
                ],
                name="frais_unique_etudiant_annee",
            ),
            models.CheckConstraint(
                condition=Q(montant_total__gt=0),
                name="frais_montant_total_positif",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "annee_universitaire",
                    "est_actif",
                ],
                name="frais_annee_actif_idx",
            ),
            models.Index(
                fields=["etudiant"],
                name="frais_etudiant_idx",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        if (
            self.etudiant_id
            and self.etudiant.statut != "ACTIF"
        ):
            erreurs["etudiant"] = (
                "Les frais ne peuvent être attribués "
                "qu'à un étudiant actif."
            )

        if (
            self.annee_universitaire_id
            and self.annee_universitaire.statut == "CLOTUREE"
            and not self.pk
        ):
            erreurs["annee_universitaire"] = (
                "Il n'est pas possible de créer de nouveaux frais "
                "pour une année universitaire clôturée."
            )

        if (
            self.montant_total is not None
            and self.montant_total <= 0
        ):
            erreurs["montant_total"] = (
                "Le montant total doit être strictement positif."
            )

        if self.pk:
            ancien = FraisHebergement.objects.filter(
                pk=self.pk
            ).first()

            if (
                ancien
                and self.montant_total is not None
                and self.montant_total < self.montant_paye
            ):
                erreurs["montant_total"] = (
                    "Le montant total ne peut pas être inférieur "
                    "au montant déjà payé."
                )

        if erreurs:
            raise ValidationError(erreurs)

    @property
    def montant_paye(self):
        # Un frais qui n'est pas encore enregistré
        # ne peut pas avoir de paiements associés.
        if not self.pk:
            return Decimal("0.00")

        resultat = self.paiements.filter(
        statut=Paiement.Statut.VALIDE,
        ).aggregate(
        total=Sum("montant")
        )

        return resultat["total"] or Decimal("0.00")


    @property
    def montant_restant(self):
        montant_total = (
        self.montant_total
        if self.montant_total is not None
        else Decimal("0.00")
    )

        restant = montant_total - self.montant_paye

        return max(
        restant,
        Decimal("0.00"),
    )

    @property
    def statut_financier(self):
        if self.montant_paye <= 0:
            if timezone.localdate() > self.date_echeance:
                return "En retard"
            return "Non payé"

        if self.montant_restant <= 0:
            return "Payé"

        if timezone.localdate() > self.date_echeance:
            return "Partiellement payé — en retard"

        return "Partiellement payé"

    @property
    def est_solde(self):
        return self.montant_restant <= 0

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.etudiant.matricule} — "
            f"{self.annee_universitaire.libelle} — "
            f"{self.montant_total} DH"
        )



def valider_taille_preuve_paiement(fichier):
    """Limite une preuve de paiement à 5 Mo."""
    taille_maximale = 5 * 1024 * 1024

    if fichier.size > taille_maximale:
        raise ValidationError(
            "La preuve de paiement ne doit pas dépasser 5 Mo."
        )


class Paiement(models.Model):
    class ModePaiement(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        VIREMENT = "VIREMENT", "Virement bancaire"
        CARTE = "CARTE", "Carte bancaire"
        CHEQUE = "CHEQUE", "Chèque"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        EN_ATTENTE = "ATTENTE", "En attente"
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"

    class Origine(models.TextChoices):
        ADMINISTRATION = "ADMIN", "Administration"
        ETUDIANT = "ETUDIANT", "Étudiant"

    frais_hebergement = models.ForeignKey(
        FraisHebergement,
        on_delete=models.PROTECT,
        related_name="paiements",
        verbose_name="Frais d'hébergement",
    )

    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            )
        ],
        verbose_name="Montant payé",
    )

    date_paiement = models.DateField(
        default=timezone.localdate,
        verbose_name="Date du paiement",
    )

    mode_paiement = models.CharField(
        max_length=10,
        choices=ModePaiement.choices,
        verbose_name="Mode de paiement",
    )

    reference = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Référence du paiement",
    )

    origine = models.CharField(
        max_length=10,
        choices=Origine.choices,
        default=Origine.ADMINISTRATION,
        verbose_name="Origine de la déclaration",
    )

    preuve_paiement = models.FileField(
        upload_to="paiements/preuves/%Y/%m/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "jpg",
                    "jpeg",
                    "png",
                ]
            ),
            valider_taille_preuve_paiement,
        ],
        blank=True,
        null=True,
        verbose_name="Preuve de paiement",
    )

    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        verbose_name="Statut",
    )

    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire",
    )

    motif_annulation = models.TextField(
        blank=True,
        verbose_name="Motif d'annulation",
    )

    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="paiements_enregistres",
        blank=True,
        null=True,
        limit_choices_to={
            "role__in": [
                "ADMIN",
                "RESP",
            ],
        },
        verbose_name="Enregistré par",
    )

    date_validation = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de validation",
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
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

        ordering = [
            "-date_paiement",
            "-date_creation",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    montant__gt=0
                ),
                name="paiement_montant_positif",
            ),
        ]

        indexes = [
            models.Index(
                fields=["statut"],
                name="paiement_statut_idx",
            ),
            models.Index(
                fields=["date_paiement"],
                name="paiement_date_idx",
            ),
            models.Index(
                fields=[
                    "frais_hebergement",
                    "statut",
                ],
                name="paiement_frais_statut_idx",
            ),
            models.Index(
                fields=["origine"],
                name="paiement_origine_idx",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        if (
            self.montant is not None
            and self.montant <= 0
        ):
            erreurs["montant"] = (
                "Le montant du paiement doit être "
                "strictement positif."
            )

        if (
            self.frais_hebergement_id
            and not self.frais_hebergement.est_actif
        ):
            erreurs["frais_hebergement"] = (
                "Ces frais d'hébergement sont désactivés."
            )

        if (
            self.statut == self.Statut.ANNULE
            and not self.motif_annulation.strip()
        ):
            erreurs["motif_annulation"] = (
                "Le motif d'annulation est obligatoire."
            )

        # Une déclaration faite par un étudiant doit être
        # vérifiable par l'administration.
        if self.origine == self.Origine.ETUDIANT:
            if (
                self.mode_paiement
                == self.ModePaiement.ESPECES
            ):
                erreurs["mode_paiement"] = (
                    "Un paiement en espèces doit être "
                    "enregistré directement par l'administration."
                )

            if not self.reference:
                erreurs["reference"] = (
                    "La référence du paiement est obligatoire."
                )

            if not self.preuve_paiement:
                erreurs["preuve_paiement"] = (
                    "La preuve de paiement est obligatoire."
                )

        # Un paiement validé ne peut pas provoquer
        # un dépassement du montant total des frais.
        if (
            self.frais_hebergement_id
            and self.montant is not None
            and self.statut == self.Statut.VALIDE
        ):
            total_autres_paiements_valides = (
                self.frais_hebergement
                .paiements
                .filter(
                    statut=self.Statut.VALIDE,
                )
                .exclude(pk=self.pk)
                .aggregate(
                    total=Sum("montant")
                )["total"]
                or Decimal("0.00")
            )

            montant_restant_avant_validation = (
                self.frais_hebergement.montant_total
                - total_autres_paiements_valides
            )

            if (
                self.montant
                > montant_restant_avant_validation
            ):
                erreurs["montant"] = (
                    "Le paiement dépasse le montant "
                    "restant à régler, qui est de "
                    f"{max(montant_restant_avant_validation, Decimal('0.00'))} DH."
                )

        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        if (
            self.statut == self.Statut.VALIDE
            and not self.date_validation
        ):
            self.date_validation = timezone.now()

        if self.statut != self.Statut.VALIDE:
            self.date_validation = None

        self.full_clean()
        super().save(*args, **kwargs)

    def valider(self):
        if self.statut == self.Statut.VALIDE:
            raise ValidationError(
                "Ce paiement est déjà validé."
            )

        if self.statut == self.Statut.ANNULE:
            raise ValidationError(
                "Un paiement annulé ne peut pas être validé."
            )

        self.statut = self.Statut.VALIDE
        self.date_validation = timezone.now()
        self.save()

    def annuler(self, motif):
        if self.statut == self.Statut.ANNULE:
            raise ValidationError(
                "Ce paiement est déjà annulé."
            )

        if not motif or not motif.strip():
            raise ValidationError(
                "Le motif d'annulation est obligatoire."
            )

        self.statut = self.Statut.ANNULE
        self.motif_annulation = motif.strip()
        self.date_validation = None
        self.save()

    @property
    def etudiant(self):
        return self.frais_hebergement.etudiant

    @property
    def annee_universitaire(self):
        return self.frais_hebergement.annee_universitaire

    def __str__(self):
        return (
            f"{self.frais_hebergement.etudiant.matricule} — "
            f"{self.montant} DH — "
            f"{self.date_paiement}"
        )
