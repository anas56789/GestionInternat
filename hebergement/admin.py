from django.contrib import admin

from .models import AnneeUniversitaire, Batiment, Chambre

from .models import (
    Affectation,
    AnneeUniversitaire,
    Batiment,
    Chambre,
    DemandeHebergement,
    Justificatif,
    Transfert,
)

@admin.register(AnneeUniversitaire)
class AnneeUniversitaireAdmin(admin.ModelAdmin):
    list_display = (
        "libelle",
        "date_debut",
        "date_fin",
        "statut",
    )

    list_filter = (
        "statut",
        "date_debut",
    )

    search_fields = (
        "libelle",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )


@admin.register(Batiment)
class BatimentAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "nom",
        "nombre_etages",
        "statut",
        "capacite_totale",
        "nombre_places_disponibles",
        "taux_occupation",
    )

    list_filter = (
        "statut",
    )

    search_fields = (
        "code",
        "nom",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )


@admin.register(Chambre)
class ChambreAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "batiment",
        "etage",
        "capacite",
        "type_chambre",
        "etat",
        "est_active",
        "nombre_places_occupees",
        "nombre_places_disponibles",
    )

    list_filter = (
        "batiment",
        "etage",
        "type_chambre",
        "etat",
        "est_active",
    )

    search_fields = (
        "numero",
        "batiment__code",
        "batiment__nom",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )

class JustificatifInline(admin.TabularInline):
    model = Justificatif
    extra = 0
    fields = (
        "type_document",
        "fichier",
        "statut_validation",
        "commentaire_validation",
    )


@admin.register(DemandeHebergement)
class DemandeHebergementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "etudiant",
        "annee_universitaire",
        "statut",
        "date_creation",
        "date_soumission",
        "date_decision",
        "traitee_par",
    )

    list_filter = (
        "statut",
        "annee_universitaire",
        "date_creation",
    )

    search_fields = (
        "etudiant__matricule",
        "etudiant__cne",
        "etudiant__utilisateur__first_name",
        "etudiant__utilisateur__last_name",
        "motif",
    )

    autocomplete_fields = (
        "etudiant",
        "traitee_par",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )

    inlines = [
        JustificatifInline,
    ]

    fieldsets = (
        (
            "Demande",
            {
                "fields": (
                    "etudiant",
                    "annee_universitaire",
                    "motif",
                    "distance_domicile",
                    "situation_sociale",
                    "commentaire",
                )
            },
        ),
        (
            "Traitement",
            {
                "fields": (
                    "statut",
                    "motif_decision",
                    "traitee_par",
                    "date_soumission",
                    "date_decision",
                )
            },
        ),
        (
            "Traçabilité",
            {
                "fields": (
                    "date_creation",
                    "date_modification",
                )
            },
        ),
    )


@admin.register(Justificatif)
class JustificatifAdmin(admin.ModelAdmin):
    list_display = (
        "type_document",
        "demande",
        "nom_original",
        "statut_validation",
        "date_ajout",
    )

    list_filter = (
        "type_document",
        "statut_validation",
        "date_ajout",
    )

    search_fields = (
        "nom_original",
        "demande__etudiant__matricule",
        "demande__etudiant__cne",
    )

    autocomplete_fields = (
        "demande",
    )

    readonly_fields = (
        "nom_original",
        "date_ajout",
    )

@admin.register(Affectation)
class AffectationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "etudiant",
        "chambre",
        "annee_universitaire",
        "statut",
        "date_entree_prevue",
        "date_entree_reelle",
        "date_sortie_prevue",
        "date_sortie_reelle",
    )

    list_filter = (
        "statut",
        "annee_universitaire",
        "chambre__batiment",
        "date_entree_prevue",
    )

    search_fields = (
        "etudiant__matricule",
        "etudiant__cne",
        "etudiant__utilisateur__first_name",
        "etudiant__utilisateur__last_name",
        "chambre__numero",
        "chambre__batiment__code",
    )

    autocomplete_fields = (
        "etudiant",
        "chambre",
        "demande_hebergement",
        "creee_par",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )

    fieldsets = (
        (
            "Affectation",
            {
                "fields": (
                    "etudiant",
                    "demande_hebergement",
                    "annee_universitaire",
                    "chambre",
                    "statut",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "date_entree_prevue",
                    "date_entree_reelle",
                    "date_sortie_prevue",
                    "date_sortie_reelle",
                )
            },
        ),
        (
            "Sortie",
            {
                "fields": (
                    "motif_sortie",
                )
            },
        ),
        (
            "Traçabilité",
            {
                "fields": (
                    "creee_par",
                    "date_creation",
                    "date_modification",
                )
            },
        ),
    )


@admin.register(Transfert)
class TransfertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "etudiant",
        "ancienne_chambre",
        "nouvelle_chambre",
        "date_transfert",
        "effectue_par",
    )

    list_filter = (
        "date_transfert",
        "ancienne_affectation__chambre__batiment",
        "nouvelle_affectation__chambre__batiment",
    )

    search_fields = (
        "ancienne_affectation__etudiant__matricule",
        "ancienne_affectation__etudiant__cne",
        "motif",
    )

    autocomplete_fields = (
        "ancienne_affectation",
        "nouvelle_affectation",
        "effectue_par",
    )

    readonly_fields = (
        "date_creation",
    )

    @admin.display(description="Étudiant")
    def etudiant(self, obj):
        return obj.ancienne_affectation.etudiant

    @admin.display(description="Ancienne chambre")
    def ancienne_chambre(self, obj):
        return obj.ancienne_affectation.chambre

    @admin.display(description="Nouvelle chambre")
    def nouvelle_chambre(self, obj):
        return obj.nouvelle_affectation.chambre