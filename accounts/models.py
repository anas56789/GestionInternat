from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    class Role(models.TextChoices):
        ADMINISTRATEUR = "ADMIN", "Administrateur"
        RESPONSABLE = "RESP", "Responsable de l'internat"
        ETUDIANT = "ETUD", "Étudiant"

    email = models.EmailField(
        unique=True,
        verbose_name="Adresse électronique",
    )

    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Téléphone",
    )

    role = models.CharField(
        max_length=5,
        choices=Role.choices,
        default=Role.ETUDIANT,
        verbose_name="Rôle",
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        nom_complet = self.get_full_name().strip()
        return nom_complet or self.username