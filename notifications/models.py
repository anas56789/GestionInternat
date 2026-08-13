from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class TypeNotification(models.TextChoices):
        DEMANDE = (
            "DEMANDE",
            "Demande d'hébergement",
        )

        AFFECTATION = (
            "AFFECTATION",
            "Affectation",
        )

        PAIEMENT = (
            "PAIEMENT",
            "Paiement",
        )

        RECLAMATION = (
            "RECLAMATION",
            "Réclamation",
        )

        SYSTEME = (
            "SYSTEME",
            "Système",
        )

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Utilisateur",
    )

    titre = models.CharField(
        max_length=200,
        verbose_name="Titre",
    )

    message = models.TextField(
        verbose_name="Message",
    )

    type_notification = models.CharField(
        max_length=15,
        choices=TypeNotification.choices,
        default=TypeNotification.SYSTEME,
        verbose_name="Type de notification",
    )

    est_lue = models.BooleanField(
        default=False,
        verbose_name="Lue",
    )

    lien = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Lien interne",
        help_text=(
            "Exemple : "
            "/hebergement/etudiant/demandes/5/"
        ),
    )

    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    date_lecture = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de lecture",
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

        ordering = [
            "-date_creation",
        ]

        indexes = [
            models.Index(
                fields=[
                    "utilisateur",
                    "est_lue",
                ],
                name="notification_user_lue_idx",
            ),
            models.Index(
                fields=[
                    "type_notification",
                ],
                name="notification_type_idx",
            ),
            models.Index(
                fields=[
                    "date_creation",
                ],
                name="notification_date_idx",
            ),
        ]

    def marquer_comme_lue(self):
        """
        Marque la notification comme lue et renseigne
        automatiquement la date de lecture.
        """

        if self.est_lue:
            return

        self.est_lue = True
        self.date_lecture = timezone.now()

        self.save(
            update_fields=[
                "est_lue",
                "date_lecture",
            ]
        )

    def marquer_comme_non_lue(self):
        """
        Replace la notification dans les notifications
        non lues.
        """

        if not self.est_lue:
            return

        self.est_lue = False
        self.date_lecture = None

        self.save(
            update_fields=[
                "est_lue",
                "date_lecture",
            ]
        )

    def __str__(self):
        return (
            f"{self.utilisateur} — "
            f"{self.titre}"
        )


def creer_notification(
    utilisateur,
    titre,
    message,
    type_notification=Notification.TypeNotification.SYSTEME,
    lien="",
):
    """
    Crée une notification destinée à un utilisateur.
    """

    if utilisateur is None:
        return None

    return Notification.objects.create(
        utilisateur=utilisateur,
        titre=titre,
        message=message,
        type_notification=type_notification,
        lien=lien,
    )
