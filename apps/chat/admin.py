from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 1
    readonly_fields = ("created_at",)
    fields = ("content", "is_from_dj", "is_read", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "customer_email", "booking", "is_archived", "updated_at")
    list_filter = ("is_archived",)
    search_fields = ("customer_name", "customer_email", "session_key")
    readonly_fields = ("session_key", "created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "is_from_dj", "is_read", "created_at")
    list_filter = ("is_from_dj", "is_read")
    readonly_fields = ("created_at",)
