from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from finances.models import FraisHebergement
from notifications.models import (
    Notification,
    creer_notification,
)


class Command(BaseCommand):
    help = (
        "Envoie aux étudiants les rappels concernant "
        "les échéances des frais d'hébergement."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Affiche les rappels qui seraient envoyés "
                "sans créer de notification."
            ),
        )

    def handle(self, *args, **options):
        aujourd_hui = timezone.localdate()
        simulation = options["dry_run"]

        frais_actifs = (
            FraisHebergement.objects
            .filter(
                est_actif=True,
            )
            .select_related(
                "etudiant",
                "etudiant__utilisateur",
                "annee_universitaire",
            )
            .prefetch_related(
                "paiements",
            )
            .order_by(
                "date_echeance",
                "etudiant__matricule",
            )
        )

        nombre_envoyes = 0
        nombre_ignores = 0
        nombre_simules = 0

        for frais in frais_actifs:
            montant_restant = frais.montant_restant

            if montant_restant <= Decimal("0.00"):
                nombre_ignores += 1
                continue

            jours_restants = (
                frais.date_echeance
                - aujourd_hui
            ).days

            donnees_rappel = self._obtenir_rappel(
                frais=frais,
                jours_restants=jours_restants,
                montant_restant=montant_restant,
            )

            if donnees_rappel is None:
                nombre_ignores += 1
                continue

            titre, message = donnees_rappel
            utilisateur = frais.etudiant.utilisateur

            deja_envoyee = (
                Notification.objects
                .filter(
                    utilisateur=utilisateur,
                    titre=titre,
                    date_creation__date=aujourd_hui,
                )
                .exists()
            )

            if deja_envoyee:
                self.stdout.write(
                    self.style.WARNING(
                        "Déjà envoyée aujourd'hui : "
                        f"{frais.etudiant.matricule} — "
                        f"{titre}"
                    )
                )

                nombre_ignores += 1
                continue

            if simulation:
                self.stdout.write(
                    self.style.NOTICE(
                        "[SIMULATION] "
                        f"{frais.etudiant.matricule} — "
                        f"{titre}"
                    )
                )

                nombre_simules += 1
                continue

            creer_notification(
                utilisateur=utilisateur,
                titre=titre,
                message=message,
                type_notification="PAIEMENT",
                lien="/finances/ma-situation/",
            )

            nombre_envoyes += 1

            self.stdout.write(
                self.style.SUCCESS(
                    "Notification envoyée : "
                    f"{frais.etudiant.matricule} — "
                    f"{titre}"
                )
            )

        self.stdout.write("")

        if simulation:
            self.stdout.write(
                self.style.SUCCESS(
                    "Simulation terminée : "
                    f"{nombre_simules} rappel(s) détecté(s), "
                    f"{nombre_ignores} dossier(s) ignoré(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Traitement terminé : "
                    f"{nombre_envoyes} notification(s) envoyée(s), "
                    f"{nombre_ignores} dossier(s) ignoré(s)."
                )
            )

    def _obtenir_rappel(
        self,
        *,
        frais,
        jours_restants,
        montant_restant,
    ):
        annee = frais.annee_universitaire.libelle
        echeance = frais.date_echeance.strftime(
            "%d/%m/%Y"
        )

        if jours_restants in {7, 3, 1}:
            unite = (
                "jour"
                if jours_restants == 1
                else "jours"
            )

            titre = (
                "Rappel : échéance de paiement "
                f"dans {jours_restants} {unite}"
            )

            message = (
                "Il vous reste "
                f"{montant_restant} DH à régler pour "
                f"l'année universitaire {annee}. "
                f"L'échéance est fixée au {echeance}."
            )

            return titre, message

        if jours_restants == 0:
            titre = "Échéance de paiement aujourd'hui"

            message = (
                "L'échéance de vos frais d'hébergement "
                f"pour l'année {annee} est aujourd'hui. "
                f"Le montant restant est de "
                f"{montant_restant} DH."
            )

            return titre, message

        jours_retard = abs(jours_restants)

        if jours_restants < 0 and jours_retard in {
            1,
            7,
            14,
            30,
        }:
            unite = (
                "jour"
                if jours_retard == 1
                else "jours"
            )

            titre = (
                "Paiement en retard de "
                f"{jours_retard} {unite}"
            )

            message = (
                "Votre échéance de paiement du "
                f"{echeance} est dépassée. "
                f"Le montant restant à régler est de "
                f"{montant_restant} DH pour "
                f"l'année universitaire {annee}."
            )

            return titre, message

        return None
