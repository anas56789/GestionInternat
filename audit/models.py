from django.conf import settings
from django.db import models


class HistoriqueAction(models.Model):
    class TypeAction(models.TextChoices):
        CREATION = "CREATION", "Création"
        MODIFICATION = "MODIFICATION", "Modification"
        VALIDATION = "VALIDATION", "Validation"
        ANNULATION = "ANNULATION", "Annulation"
        AFFECTATION = "AFFECTATION", "Affectation"
        TRANSFERT = "TRANSFERT", "Transfert"
        CLOTURE = "CLOTURE", "Clôture"
        TRAITEMENT = "TRAITEMENT", "Traitement"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="actions_audit",
        null=True,
        blank=True,
        verbose_name="Utilisateur",
    )

    type_action = models.CharField(
        max_length=20,
        choices=TypeAction.choices,
        verbose_name="Type d'action",
    )

    entite = models.CharField(
        max_length=100,
        verbose_name="Entité",
    )

    identifiant_entite = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Identifiant de l'entité",
    )

    description = models.TextField(
        verbose_name="Description",
    )

    anciennes_valeurs = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Anciennes valeurs",
    )

    nouvelles_valeurs = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Nouvelles valeurs",
    )

    adresse_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Adresse IP",
    )

    date_action = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de l'action",
    )

    class Meta:
        verbose_name = "Historique d'action"
        verbose_name_plural = "Historique des actions"
        ordering = ["-date_action"]

    @classmethod
    def enregistrer_action(
        cls,
        utilisateur,
        type_action,
        entite,
        identifiant_entite,
        description,
        request=None,
        anciennes_valeurs=None,
        nouvelles_valeurs=None,
    ):
        adresse_ip = None

        if request:
            adresse_ip = request.META.get("REMOTE_ADDR")

            adresse_transmise = request.META.get(
                "HTTP_X_FORWARDED_FOR"
            )

            if adresse_transmise:
                adresse_ip = (
                    adresse_transmise.split(",")[0].strip()
                )

        return cls.objects.create(
            utilisateur=utilisateur,
            type_action=type_action,
            entite=entite,
            identifiant_entite=str(
                identifiant_entite or ""
            ),
            description=description,
            anciennes_valeurs=anciennes_valeurs,
            nouvelles_valeurs=nouvelles_valeurs,
            adresse_ip=adresse_ip,
        )

    def __str__(self):
        return (
            f"{self.type_action} — "
            f"{self.entite} — "
            f"{self.date_action:%d/%m/%Y %H:%M}"
        )