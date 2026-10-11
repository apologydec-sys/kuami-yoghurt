from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a default SiteSettings row if one does not already exist."

    def handle(self, *args, **options):
        from apps.core.models import SiteSettings

        settings, created = SiteSettings.objects.get_or_create(pk=1)
        if created:
            self.stdout.write(self.style.SUCCESS("Default SiteSettings created."))
        else:
            self.stdout.write("SiteSettings already exist — no changes made.")
