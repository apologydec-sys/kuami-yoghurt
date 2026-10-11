from django.contrib import admin

from .models import Biography, ContactMessage, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Site Identity", {"fields": ("site_name", "tagline", "profile_image", "is_active")}),
        ("About / Biography", {"fields": ("about_text", "biography")}),
        ("Contact & Social", {"fields": (
            "whatsapp_number", "email",
            "facebook_url", "instagram_url", "twitter_url", "youtube_url",
        )}),
    )


@admin.register(Biography)
class BiographyAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("title", "body")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("ip_address", "created_at")
    date_hierarchy = "created_at"
