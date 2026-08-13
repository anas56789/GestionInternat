from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Informations de l'internat",
            {
                "fields": (
                    "telephone",
                    "role",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Informations de l'internat",
            {
                "fields": (
                    "email",
                    "telephone",
                    "role",
                    "is_active",
                )
            },
        ),
    )

    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
    )