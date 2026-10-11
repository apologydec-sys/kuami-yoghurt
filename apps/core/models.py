from django.db import models
from cloudinary.models import CloudinaryField


class SiteSettings(models.Model):
    """Singleton model for global site configuration."""

    site_name = models.CharField(max_length=200, default="DJ Kuami Yoghurt")
    tagline = models.CharField(max_length=500, blank=True)
    about_text = models.TextField(blank=True)
    biography = models.TextField(blank=True)
    profile_image = CloudinaryField("profile_image", blank=True, null=True)
    whatsapp_number = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # Enforce singleton — only one row allowed.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Biography(models.Model):
    """Rich biography block for the About page."""

    title = models.CharField(max_length=200, default="About DJ Kuami Yoghurt")
    body = models.TextField()
    profile_image = CloudinaryField("biography_profile_image", blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Biography"
        verbose_name_plural = "Biographies"

    def __str__(self):
        return self.title


class ContactMessage(models.Model):
    """Messages submitted through the public contact form."""

    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=300)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

    def __str__(self):
        return f"{self.name} — {self.subject}"
