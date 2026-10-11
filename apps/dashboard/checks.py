from django.conf import settings
from django.core.checks import Warning, register


@register()
def cloudinary_configuration_check(app_configs, **kwargs):
    if not settings.CLOUDINARY_MISSING_SETTINGS:
        return []
    return [
        Warning(
            "Cloudinary credentials are not configured; portal uploads will be unavailable.",
            hint=(
                "Set CLOUDINARY_URL or CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, "
                "and CLOUDINARY_API_SECRET in the local .env file or hosting environment."
            ),
            id="dashboard.W001",
        )
    ]
