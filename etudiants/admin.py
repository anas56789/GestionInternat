from django.contrib import admin

from .models import Etudiant


@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    list_display = (
        "matricule",
        "cne",
        "nom_complet",
        "filiere",
        "niveau_etude",
        "ville_origine",
        "statut",
    )

    list_filter = (
        "statut",
        "sexe",
        "filiere",
        "niveau_etude",
        "ville_origine",
    )

    search_fields = (
        "matricule",
        "cne",
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
        "utilisateur__email",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )

    fieldsets = (
        (
            "Compte",
            {
                "fields": (
                    "utilisateur",
                    "matricule",
                    "cne",
                    "statut",
                )
            },
        ),
        (
            "Informations personnelles",
            {
                "fields": (
                    "date_naissance",
                    "sexe",
                    "adresse",
                    "ville_origine",
                    "photo",
                )
            },
        ),
        (
            "Informations académiques",
            {
                "fields": (
                    "filiere",
                    "niveau_etude",
                )
            },
        ),
        (
            "Contact d'urgence",
            {
                "fields": (
                    "nom_contact_urgence",
                    "telephone_contact_urgence",
                    "lien_contact_urgence",
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

    @admin.display(description="Nom complet")
    def nom_complet(self, obj):
        return obj.utilisateur.get_full_name() or obj.utilisateur.username

autocomplete_fields = ("etudiant", "traitee_par")