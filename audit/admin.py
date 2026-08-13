from django.contrib import admin

from .models import HistoriqueAction


@admin.register(HistoriqueAction)
class HistoriqueActionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "utilisateur",
        "type_action",
        "entite",
        "identifiant_entite",
        "adresse_ip",
        "date_action",
    )

    list_filter = (
        "type_action",
        "entite",
        "date_action",
    )

    search_fields = (
        "description",
        "entite",
        "identifiant_entite",
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
        "utilisateur__email",
    )

    autocomplete_fields = (
        "utilisateur",
    )

    readonly_fields = (
        "utilisateur",
        "type_action",
        "entite",
        "identifiant_entite",
        "description",
        "anciennes_valeurs",
        "nouvelles_valeurs",
        "adresse_ip",
        "date_action",
    )

    ordering = (
        "-date_action",
    )

    date_hierarchy = "date_action"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser