from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum


class Command(BaseCommand):
    help = "Contrôles de cohérence en lecture seule pour GestionInternat."

    def __init__(self):
        super().__init__()
        self.ok_count = 0
        self.warn_count = 0
        self.fail_count = 0

    def ok(self, message):
        self.ok_count += 1
        self.stdout.write(self.style.SUCCESS(f"[OK] {message}"))

    def warn(self, message):
        self.warn_count += 1
        self.stdout.write(self.style.WARNING(f"[AVERTISSEMENT] {message}"))

    def fail(self, message):
        self.fail_count += 1
        self.stdout.write(self.style.ERROR(f"[ERREUR] {message}"))

    def model(self, app_label, model_name):
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            self.warn(f"Modèle {app_label}.{model_name} introuvable.")
            return None

    def fields(self, model):
        return {f.name for f in model._meta.get_fields() if hasattr(f, "name")}

    def check_active_year(self):
        M = self.model("hebergement", "AnneeUniversitaire")
        if not M or "statut" not in self.fields(M):
            return
        count = M.objects.filter(statut="ACTIVE").count()
        if count == 1:
            self.ok("Une seule année universitaire est active.")
        elif count == 0:
            self.warn("Aucune année universitaire active.")
        else:
            self.fail(f"{count} années universitaires actives simultanément.")

    def check_duplicate_active_assignments(self):
        M = self.model("hebergement", "Affectation")
        if not M:
            return
        if not {"statut", "etudiant"} <= self.fields(M):
            return
        duplicates = list(
            M.objects.filter(statut="ACTIVE")
            .values("etudiant_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        if duplicates:
            self.fail(f"{len(duplicates)} étudiant(s) ont plusieurs affectations actives.")
        else:
            self.ok("Aucune double affectation active par étudiant.")

    def check_room_capacity(self):
        Chambre = self.model("hebergement", "Chambre")
        Affectation = self.model("hebergement", "Affectation")
        if not Chambre or not Affectation:
            return
        if "capacite" not in self.fields(Chambre):
            return
        anomalies = []
        for chambre in Chambre.objects.all():
            occupation = Affectation.objects.filter(
                chambre=chambre,
                statut="ACTIVE",
            ).count()
            if occupation > chambre.capacite:
                anomalies.append((chambre.pk, occupation, chambre.capacite))
        if anomalies:
            self.fail(f"{len(anomalies)} chambre(s) dépassent leur capacité.")
            for pk, occ, cap in anomalies[:10]:
                self.stdout.write(f"    chambre #{pk}: {occ}/{cap}")
        else:
            self.ok("Aucune chambre ne dépasse sa capacité.")

    def check_room_availability(self):
        Chambre = self.model("hebergement", "Chambre")
        Affectation = self.model("hebergement", "Affectation")
        if not Chambre or not Affectation:
            return
        room_fields = self.fields(Chambre)
        anomalies = []
        for aff in Affectation.objects.filter(statut="ACTIVE").select_related("chambre"):
            ch = aff.chambre
            if "est_active" in room_fields and not ch.est_active:
                anomalies.append((aff.pk, ch.pk, "désactivée"))
            elif "etat" in room_fields and str(ch.etat).upper() in {"MAINTENANCE", "HORS_SERVICE"}:
                anomalies.append((aff.pk, ch.pk, ch.etat))
        if anomalies:
            self.fail(f"{len(anomalies)} affectation(s) active(s) utilisent une chambre indisponible.")
        else:
            self.ok("Aucune affectation active dans une chambre indisponible.")

    def check_assignment_dates(self):
        M = self.model("hebergement", "Affectation")
        if not M:
            return
        fields = self.fields(M)
        errors = 0
        for obj in M.objects.all():
            ep = getattr(obj, "date_entree_prevue", None)
            sp = getattr(obj, "date_sortie_prevue", None)
            er = getattr(obj, "date_entree_reelle", None)
            sr = getattr(obj, "date_sortie_reelle", None)
            if ep and sp and sp < ep:
                errors += 1
            if er and sr and sr < er:
                errors += 1
        if errors:
            self.fail(f"{errors} incohérence(s) de dates d'affectation.")
        else:
            self.ok("Dates des affectations cohérentes.")

    def check_requests(self):
        M = self.model("hebergement", "DemandeHebergement")
        if not M:
            return
        required = {"etudiant", "annee_universitaire", "statut"}
        if not required <= self.fields(M):
            return
        duplicates = list(
            M.objects.exclude(statut__in=["REFUSEE", "ANNULEE"])
            .values("etudiant_id", "annee_universitaire_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        if duplicates:
            self.warn(
                f"{len(duplicates)} combinaison(s) étudiant/année ont plusieurs demandes non refusées/non annulées."
            )
        else:
            self.ok("Pas de doublons anormaux de demandes par étudiant/année.")

    def check_student_profiles(self):
        User = self.model("accounts", "Utilisateur")
        Student = self.model("etudiants", "Etudiant")
        if not User or not Student:
            return
        if "role" not in self.fields(User) or "utilisateur" not in self.fields(Student):
            return
        missing = 0
        for user in User.objects.filter(role="ETUDIANT"):
            if not Student.objects.filter(utilisateur=user).exists():
                missing += 1
        if missing:
            self.warn(f"{missing} compte(s) étudiant(s) sans profil Etudiant.")
        else:
            self.ok("Tous les comptes étudiants ont un profil.")

    def check_payments(self):
        Frais = self.model("finances", "FraisHebergement")
        Paiement = self.model("finances", "Paiement")
        if not Frais or not Paiement:
            return
        f_fields = self.fields(Frais)
        p_fields = self.fields(Paiement)
        if not {"frais_hebergement", "montant", "statut"} <= p_fields:
            return
        total_field = "montant_total" if "montant_total" in f_fields else (
            "montant" if "montant" in f_fields else None
        )
        if not total_field:
            self.warn("Montant total des frais introuvable : contrôle financier partiel.")
            return
        anomalies = 0
        for frais in Frais.objects.all():
            total_due = Decimal(str(getattr(frais, total_field, 0) or 0))
            paid = (
                Paiement.objects.filter(
                    frais_hebergement=frais,
                    statut="VALIDE",
                ).aggregate(total=Sum("montant"))["total"]
                or Decimal("0")
            )
            if paid > total_due:
                anomalies += 1
        if anomalies:
            self.fail(f"{anomalies} dossier(s) financier(s) ont trop de paiements validés.")
        else:
            self.ok("Aucun dépassement de paiement validé.")

    def check_notifications(self):
        M = self.model("notifications", "Notification")
        if not M:
            return
        fields = self.fields(M)
        if not {"titre", "message"} <= fields:
            return
        bad = M.objects.filter(Q(titre="") | Q(message="")).count()
        if bad:
            self.warn(f"{bad} notification(s) ont un titre ou message vide.")
        else:
            self.ok("Aucune notification vide.")

    def check_reclamations(self):
        M = self.model("reclamations", "Reclamation")
        if not M or "statut" not in self.fields(M):
            return
        values = set(M.objects.values_list("statut", flat=True).distinct())
        allowed = {"NOUVELLE", "EN_COURS", "RESOLUE", "REJETEE"}
        unexpected = sorted(values - allowed)
        if unexpected:
            self.warn("Statuts de réclamation inattendus : " + ", ".join(unexpected))
        else:
            self.ok("Statuts des réclamations cohérents.")

    def handle(self, *args, **options):
        self.stdout.write("\n=== RÉGRESSION GESTIONINTERNAT ===")
        self.stdout.write("Lecture seule : aucune donnée ne sera modifiée.\n")

        self.check_active_year()
        self.check_duplicate_active_assignments()
        self.check_room_capacity()
        self.check_room_availability()
        self.check_assignment_dates()
        self.check_requests()
        self.check_student_profiles()
        self.check_payments()
        self.check_notifications()
        self.check_reclamations()

        self.stdout.write("\n=== RÉSUMÉ ===")
        self.stdout.write(self.style.SUCCESS(f"OK : {self.ok_count}"))
        self.stdout.write(self.style.WARNING(f"Avertissements : {self.warn_count}"))

        if self.fail_count:
            self.stdout.write(self.style.ERROR(f"Erreurs critiques : {self.fail_count}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Erreurs critiques : 0"))
