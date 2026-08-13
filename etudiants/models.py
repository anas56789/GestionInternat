from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Etudiant(models.Model):
    class Sexe(models.TextChoices):
        HOMME = "H", "Homme"
        FEMME = "F", "Femme"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        INACTIF = "INACTIF", "Inactif"
        DIPLOME = "DIPLOME", "Diplômé"
        ABANDON = "ABANDON", "Abandon"

    utilisateur = models.OneToOneField(
    "accounts.Utilisateur",
    on_delete=models.CASCADE,
    related_name="profil_etudiant",
    verbose_name="Compte utilisateur",
)

    matricule = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Matricule",
    )

    cne = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="CNE",
    )

    date_naissance = models.DateField(
        verbose_name="Date de naissance",
    )

    sexe = models.CharField(
        max_length=1,
        choices=Sexe.choices,
        verbose_name="Sexe",
    )

    adresse = models.TextField(
        verbose_name="Adresse",
    )

    ville_origine = models.CharField(
        max_length=100,
        verbose_name="Ville d'origine",
    )

    filiere = models.CharField(
        max_length=150,
        verbose_name="Filière",
    )

    niveau_etude = models.CharField(
        max_length=100,
        verbose_name="Niveau d'étude",
    )

    telephone_contact_urgence = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9 ]{9,20}$",
                message="Saisissez un numéro de téléphone valide.",
            )
        ],
        verbose_name="Téléphone du contact d'urgence",
    )

    nom_contact_urgence = models.CharField(
        max_length=150,
        verbose_name="Nom du contact d'urgence",
    )

    lien_contact_urgence = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Lien avec le contact d'urgence",
    )

    photo = models.ImageField(
        upload_to="etudiants/photos/",
        blank=True,
        null=True,
        verbose_name="Photo",
    )

    statut = models.CharField(
        max_length=10,
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
        verbose_name = "Étudiant"
        verbose_name_plural = "Étudiants"
        ordering = ["utilisateur__last_name", "utilisateur__first_name"]

    def __str__(self):
        nom_complet = self.utilisateur.get_full_name().strip()
        return f"{self.matricule} — {nom_complet or self.utilisateur.username}"