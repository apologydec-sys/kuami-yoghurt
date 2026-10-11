from django.contrib import admin

from .models import GalleryCategory, GalleryImage


@admin.register(GalleryCategory)
class GalleryCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_published", "is_featured", "order", "created_at")
    list_filter = ("is_published", "is_featured", "category")
    search_fields = ("title", "description")
    date_hierarchy = "created_at"
