def notifications_non_lues(request):
    if not request.user.is_authenticated:
        return {
            "nombre_notifications_non_lues": 0,
        }

    return {
        "nombre_notifications_non_lues": (
            request.user.notifications.filter(
                est_lue=False,
            ).count()
        ),
    }
