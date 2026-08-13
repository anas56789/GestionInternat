from django.contrib import admin

from .models import FraisHebergement, Paiement


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0

    fields = (
        "montant",
        "date_paiement",
        "mode_paiement",
        "reference",
        "statut",
    )

    readonly_fields = (
        "date_validation",
    )


@admin.register(FraisHebergement)
class FraisHebergementAdmin(admin.ModelAdmin):
    list_display = (
        "etudiant",
        "annee_universitaire",
        "montant_total",
        "afficher_montant_paye",
        "afficher_montant_restant",
        "afficher_statut_financier",
        "date_echeance",
        "est_actif",
    )

    list_filter = (
        "annee_universitaire",
        "est_actif",
        "date_echeance",
    )

    search_fields = (
        "etudiant__matricule",
        "etudiant__cne",
        "etudiant__utilisateur__first_name",
        "etudiant__utilisateur__last_name",
        "annee_universitaire__libelle",
    )

    autocomplete_fields = (
        "etudiant",
        "cree_par",
    )

    readonly_fields = (
        "afficher_montant_paye",
        "afficher_montant_restant",
        "afficher_statut_financier",
        "date_creation",
        "date_modification",
    )

    inlines = [
        PaiementInline,
    ]

    fieldsets = (
        (
            "Frais d'hébergement",
            {
                "fields": (
                    "etudiant",
                    "annee_universitaire",
                    "montant_total",
                    "date_echeance",
                    "est_actif",
                    "commentaire",
                )
            },
        ),
        (
            "Situation financière",
            {
                "fields": (
                    "afficher_montant_paye",
                    "afficher_montant_restant",
                    "afficher_statut_financier",
                )
            },
        ),
        (
            "Traçabilité",
            {
                "fields": (
                    "cree_par",
                    "date_creation",
                    "date_modification",
                )
            },
        ),
    )

    @admin.display(description="Montant payé")
    def afficher_montant_paye(self, obj):
        if not obj.pk:
            return "0,00 DH"

        return f"{obj.montant_paye} DH"

    @admin.display(description="Montant restant")
    def afficher_montant_restant(self, obj):
        if not obj.pk:
            return "—"

        return f"{obj.montant_restant} DH"

    @admin.display(description="Statut financier")
    def afficher_statut_financier(self, obj):
        if not obj.pk:
            return "—"

        return obj.statut_financier


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "afficher_etudiant",
        "frais_hebergement",
        "montant",
        "date_paiement",
        "mode_paiement",
        "reference",
        "statut",
        "enregistre_par",
    )

    list_filter = (
        "statut",
        "mode_paiement",
        "date_paiement",
        "frais_hebergement__annee_universitaire",
    )

    search_fields = (
        "reference",
        "frais_hebergement__etudiant__matricule",
        "frais_hebergement__etudiant__cne",
        "frais_hebergement__etudiant__utilisateur__first_name",
        "frais_hebergement__etudiant__utilisateur__last_name",
    )

    autocomplete_fields = (
        "frais_hebergement",
        "enregistre_par",
    )

    readonly_fields = (
        "date_validation",
        "date_creation",
        "date_modification",
    )

    fieldsets = (
        (
            "Paiement",
            {
                "fields": (
                    "frais_hebergement",
                    "montant",
                    "date_paiement",
                    "mode_paiement",
                    "reference",
                    "statut",
                )
            },
        ),
        (
            "Informations complémentaires",
            {
                "fields": (
                    "commentaire",
                    "motif_annulation",
                )
            },
        ),
        (
            "Traçabilité",
            {
                "fields": (
                    "enregistre_par",
                    "date_validation",
                    "date_creation",
                    "date_modification",
                )
            },
        ),
    )

    @admin.display(description="Étudiant")
    def afficher_etudiant(self, obj):
        return obj.frais_hebergement.etudiant