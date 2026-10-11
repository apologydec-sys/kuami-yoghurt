from .models import SiteSettings


def site_settings(request):
    """Make SiteSettings available to every template."""
    return {"site_settings": SiteSettings.objects.first()}
