from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from etudiants.models import Etudiant
from hebergement.models import Chambre


def valider_taille_piece_jointe(fichier):
    """Limite chaque pièce jointe à 5 Mo."""
    taille_maximale = 5 * 1024 * 1024

    if fichier.size > taille_maximale:
        raise ValidationError(
            "La taille du fichier ne doit pas dépasser 5 Mo."
        )


class Reclamation(models.Model):
    class Categorie(models.TextChoices):
        ELECTRICITE = "ELECTRICITE", "Électricité"
        PLOMBERIE = "PLOMBERIE", "Plomberie"
        MOBILIER = "MOBILIER", "Mobilier"
        INTERNET = "INTERNET", "Connexion Internet"
        PROPRETE = "PROPRETE", "Propreté"
        SECURITE = "SECURITE", "Sécurité"
        CONFLIT = "CONFLIT", "Conflit entre étudiants"
        AUTRE = "AUTRE", "Autre"

    class Priorite(models.TextChoices):
        BASSE = "BASSE", "Basse"
        NORMALE = "NORMALE", "Normale"
        HAUTE = "HAUTE", "Haute"
        URGENTE = "URGENTE", "Urgente"

    class Statut(models.TextChoices):
        NOUVELLE = "NOUVELLE", "Nouvelle"
        EN_COURS = "EN_COURS", "En cours de traitement"
        RESOLUE = "RESOLUE", "Résolue"
        REJETEE = "REJETEE", "Rejetée"
        FERMEE = "FERMEE", "Fermée"

    etudiant = models.ForeignKey(
        Etudiant,
        on_delete=models.PROTECT,
        related_name="reclamations",
        verbose_name="Étudiant",
    )

    chambre = models.ForeignKey(
        Chambre,
        on_delete=models.PROTECT,
        related_name="reclamations",
        blank=True,
        null=True,
        verbose_name="Chambre concernée",
    )

    titre = models.CharField(
        max_length=200,
        verbose_name="Titre",
    )

    description = models.TextField(
        verbose_name="Description du problème",
    )

    categorie = models.CharField(
        max_length=15,
        choices=Categorie.choices,
        verbose_name="Catégorie",
    )

    priorite = models.CharField(
        max_length=10,
        choices=Priorite.choices,
        default=Priorite.NORMALE,
        verbose_name="Priorité",
    )

    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.NOUVELLE,
        verbose_name="Statut",
    )

    piece_jointe = models.FileField(
        upload_to="reclamations/pieces_jointes/%Y/%m/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "jpg",
                    "jpeg",
                    "png",
                ]
            ),
            valider_taille_piece_jointe,
        ],
        blank=True,
        null=True,
        verbose_name="Pièce jointe",
    )

    nom_original_piece = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nom original de la pièce jointe",
    )

    reponse = models.TextField(
        blank=True,
        verbose_name="Réponse du responsable",
    )

    motif_rejet = models.TextField(
        blank=True,
        verbose_name="Motif du rejet",
    )

    traitee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reclamations_traitees",
        blank=True,
        null=True,
        limit_choices_to={
            "role__in": ["ADMIN", "RESP"],
        },
        verbose_name="Traitée par",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification",
    )

    date_prise_en_charge = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de prise en charge",
    )

    date_resolution = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de résolution",
    )

    date_fermeture = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de fermeture",
    )

    class Meta:
        verbose_name = "Réclamation"
        verbose_name_plural = "Réclamations"
        ordering = [
            "-date_creation",
        ]

        indexes = [
            models.Index(
                fields=["statut"],
                name="reclamation_statut_idx",
            ),
            models.Index(
                fields=["priorite"],
                name="reclamation_priorite_idx",
            ),
            models.Index(
                fields=["categorie"],
                name="reclamation_categorie_idx",
            ),
            models.Index(
                fields=["etudiant", "statut"],
                name="reclamation_etud_statut_idx",
            ),
        ]

    def clean(self):
        super().clean()

        erreurs = {}

        if (
            self.etudiant_id
            and self.etudiant.statut != Etudiant.Statut.ACTIF
        ):
            erreurs["etudiant"] = (
                "Seul un étudiant actif peut déposer "
                "une réclamation."
            )

        if self.chambre_id and self.etudiant_id:
            affectation_active = self.etudiant.affectations.filter(
                statut="ACTIVE",
                chambre_id=self.chambre_id,
            ).exists()

            if not affectation_active:
                erreurs["chambre"] = (
                    "La chambre choisie ne correspond pas "
                    "à l'affectation active de cet étudiant."
                )

        if not self.titre.strip():
            erreurs["titre"] = (
                "Le titre de la réclamation est obligatoire."
            )

        if not self.description.strip():
            erreurs["description"] = (
                "La description du problème est obligatoire."
            )

        if (
            self.statut == self.Statut.EN_COURS
            and not self.traitee_par_id
        ):
            erreurs["traitee_par"] = (
                "Un responsable doit être indiqué "
                "pour une réclamation en cours."
            )

        if self.statut == self.Statut.RESOLUE:
            if not self.reponse.strip():
                erreurs["reponse"] = (
                    "Une réponse est obligatoire "
                    "pour résoudre la réclamation."
                )

            if not self.traitee_par_id:
                erreurs["traitee_par"] = (
                    "Indiquez le responsable ayant traité "
                    "la réclamation."
                )

        if self.statut == self.Statut.REJETEE:
            if not self.motif_rejet.strip():
                erreurs["motif_rejet"] = (
                    "Le motif du rejet est obligatoire."
                )

            if not self.traitee_par_id:
                erreurs["traitee_par"] = (
                    "Indiquez le responsable ayant rejeté "
                    "la réclamation."
                )

        if (
            self.statut == self.Statut.FERMEE
            and not self.date_resolution
        ):
            erreurs["statut"] = (
                "Une réclamation doit être résolue "
                "avant d'être fermée."
            )

        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        if self.piece_jointe and not self.nom_original_piece:
            self.nom_original_piece = Path(
                self.piece_jointe.name
            ).name

        if (
            self.statut == self.Statut.EN_COURS
            and not self.date_prise_en_charge
        ):
            self.date_prise_en_charge = timezone.now()

        if (
            self.statut == self.Statut.RESOLUE
            and not self.date_resolution
        ):
            self.date_resolution = timezone.now()

        if (
            self.statut == self.Statut.FERMEE
            and not self.date_fermeture
        ):
            self.date_fermeture = timezone.now()

        self.full_clean()
        super().save(*args, **kwargs)

    def prendre_en_charge(self, utilisateur):
        if self.statut != self.Statut.NOUVELLE:
            raise ValidationError(
                "Seule une nouvelle réclamation "
                "peut être prise en charge."
            )

        self.statut = self.Statut.EN_COURS
        self.traitee_par = utilisateur
        self.date_prise_en_charge = timezone.now()
        self.save()

    def resoudre(self, reponse, utilisateur):
        if self.statut not in {
            self.Statut.NOUVELLE,
            self.Statut.EN_COURS,
        }:
            raise ValidationError(
                "Cette réclamation ne peut plus être résolue."
            )

        if not reponse or not reponse.strip():
            raise ValidationError(
                "La réponse est obligatoire."
            )

        self.statut = self.Statut.RESOLUE
        self.reponse = reponse.strip()
        self.traitee_par = utilisateur
        self.date_resolution = timezone.now()
        self.save()

    def rejeter(self, motif, utilisateur):
        if self.statut not in {
            self.Statut.NOUVELLE,
            self.Statut.EN_COURS,
        }:
            raise ValidationError(
                "Cette réclamation ne peut plus être rejetée."
            )

        if not motif or not motif.strip():
            raise ValidationError(
                "Le motif du rejet est obligatoire."
            )

        self.statut = self.Statut.REJETEE
        self.motif_rejet = motif.strip()
        self.traitee_par = utilisateur
        self.save()

    def fermer(self):
        if self.statut != self.Statut.RESOLUE:
            raise ValidationError(
                "Seule une réclamation résolue "
                "peut être fermée."
            )

        self.statut = self.Statut.FERMEE
        self.date_fermeture = timezone.now()
        self.save()

    @property
    def est_ouverte(self):
        return self.statut in {
            self.Statut.NOUVELLE,
            self.Statut.EN_COURS,
        }

    def __str__(self):
        return (
            f"Réclamation #{self.pk or 'nouvelle'} — "
            f"{self.etudiant.matricule} — {self.titre}"
        )