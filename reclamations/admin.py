from django.contrib import admin

from .models import Reclamation


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titre",
        "etudiant",
        "chambre",
        "categorie",
        "priorite",
        "statut",
        "traitee_par",
        "date_creation",
    )

    list_filter = (
        "statut",
        "priorite",
        "categorie",
        "date_creation",
        "chambre__batiment",
    )

    search_fields = (
        "titre",
        "description",
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
        "traitee_par",
    )

    readonly_fields = (
        "nom_original_piece",
        "date_creation",
        "date_modification",
        "date_prise_en_charge",
        "date_resolution",
        "date_fermeture",
    )

    fieldsets = (
        (
            "Réclamation",
            {
                "fields": (
                    "etudiant",
                    "chambre",
                    "titre",
                    "description",
                    "categorie",
                    "priorite",
                    "piece_jointe",
                    "nom_original_piece",
                )
            },
        ),
        (
            "Traitement",
            {
                "fields": (
                    "statut",
                    "traitee_par",
                    "reponse",
                    "motif_rejet",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "date_creation",
                    "date_modification",
                    "date_prise_en_charge",
                    "date_resolution",
                    "date_fermeture",
                )
            },
        ),
    )

    date_hierarchy = "date_creation"

    ordering = (
        "-date_creation",
    )