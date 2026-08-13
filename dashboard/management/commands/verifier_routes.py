from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse

ROUTES = [
    "accounts:connexion",
    "accounts:espace_etudiant",
    "dashboard:accueil",
    "etudiants:liste_etudiants",
    "etudiants:mon_profil",
    "etudiants:modifier_mon_profil",
    "hebergement:mes_demandes",
    "hebergement:deposer_demande",
    "hebergement:liste_demandes_responsable",
    "hebergement:liste_demandes_a_affecter",
    "hebergement:liste_affectations_responsable",
    "hebergement:liste_transferts_responsable",
    "hebergement:liste_chambres",
    "hebergement:liste_batiments",
    "hebergement:liste_annees_universitaires",
    "finances:ma_situation_financiere",
    "finances:liste_frais",
    "finances:liste_paiements_en_attente",
    "reclamations:mes_reclamations",
    "reclamations:creer_reclamation",
    "reclamations:liste_reclamations_responsable",
    "notifications:mes_notifications",
    "notifications:marquer_toutes_lues",
    "audit:historique_actions",
]

class Command(BaseCommand):
    help = "Vérifie que les routes principales peuvent être résolues."

    def handle(self, *args, **options):
        erreurs = 0
        self.stdout.write("\n=== VÉRIFICATION DES ROUTES ===")
        for nom in ROUTES:
            try:
                url = reverse(nom)
            except NoReverseMatch as exc:
                erreurs += 1
                self.stdout.write(self.style.ERROR(f"[ERREUR] {nom}"))
                self.stdout.write(f"    {exc}")
            else:
                self.stdout.write(self.style.SUCCESS(f"[OK] {nom} -> {url}"))
        if erreurs:
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Toutes les routes principales sont valides."))
