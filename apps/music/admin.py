from django.contrib import admin

from .models import Category, Mix, Track


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Mix)
class MixAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_published", "is_featured", "play_count", "published_at")
    list_filter = ("is_published", "is_featured", "category")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("title", "mix", "category", "is_published", "is_featured", "play_count", "published_at")
    list_filter = ("is_published", "is_featured", "category")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
