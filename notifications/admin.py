from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "utilisateur",
        "titre",
        "type_notification",
        "est_lue",
        "date_creation",
        "date_lecture",
    )

    list_filter = (
        "type_notification",
        "est_lue",
        "date_creation",
    )

    search_fields = (
        "titre",
        "message",
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
        "utilisateur__email",
    )

    autocomplete_fields = (
        "utilisateur",
    )

    readonly_fields = (
        "date_creation",
        "date_lecture",
    )

    ordering = (
        "-date_creation",
    )

    date_hierarchy = "date_creation"