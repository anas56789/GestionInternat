from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Notification


def _est_responsable_ou_admin(utilisateur):
    return (
        utilisateur.is_superuser
        or getattr(utilisateur, "role", "") in {"ADMIN", "RESP"}
    )


@login_required
def mes_notifications(request):
    notifications = (
        Notification.objects
        .filter(
            utilisateur=request.user,
        )
        .order_by(
            "-date_creation",
        )
    )

    nombre_non_lues = (
        notifications
        .filter(
            est_lue=False,
        )
        .count()
    )

    contexte = {
        "notifications": notifications,
        "nombre_non_lues": nombre_non_lues,
        "nombre_notifications_non_lues": nombre_non_lues,
    }

    if _est_responsable_ou_admin(request.user):
        template = "notifications/mes_notifications.html"
    else:
        template = "notifications/etudiant/mes_notifications.html"

    return render(
        request,
        template,
        contexte,
    )


@login_required
def detail_notification(
    request,
    notification_id,
):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        utilisateur=request.user,
    )

    if not notification.est_lue:
        notification.marquer_comme_lue()

    contexte = {
        "notification": notification,
        "nombre_notifications_non_lues": (
            Notification.objects
            .filter(
                utilisateur=request.user,
                est_lue=False,
            )
            .count()
        ),
    }

    if _est_responsable_ou_admin(request.user):
        template = "notifications/detail_notification.html"
    else:
        template = "notifications/etudiant/detail_notification.html"

    return render(
        request,
        template,
        contexte,
    )


@login_required
def marquer_notification_lue(
    request,
    notification_id,
):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        utilisateur=request.user,
    )

    if request.method != "POST":
        return redirect(
            "notifications:mes_notifications",
        )

    notification.marquer_comme_lue()

    prochaine_page = request.POST.get(
        "next",
        "",
    ).strip()

    if (
        prochaine_page
        and url_has_allowed_host_and_scheme(
            url=prochaine_page,
            allowed_hosts={
                request.get_host(),
            },
            require_https=request.is_secure(),
        )
    ):
        return redirect(
            prochaine_page,
        )

    return redirect(
        "notifications:mes_notifications",
    )


@login_required
def marquer_toutes_lues(request):
    if request.method != "POST":
        return redirect(
            "notifications:mes_notifications",
        )

    notifications_non_lues = (
        Notification.objects
        .filter(
            utilisateur=request.user,
            est_lue=False,
        )
    )

    for notification in notifications_non_lues:
        notification.marquer_comme_lue()

    return redirect(
        "notifications:mes_notifications",
    )
