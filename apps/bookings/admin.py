from django.contrib import admin

from .models import Booking, BookingMessage, BookingStatusHistory, Quotation


class QuotationInline(admin.StackedInline):
    model = Quotation
    extra = 0
    can_delete = False


class BookingStatusHistoryInline(admin.TabularInline):
    model = BookingStatusHistory
    extra = 0
    readonly_fields = ("changed_at",)


class BookingMessageInline(admin.TabularInline):
    model = BookingMessage
    extra = 1
    readonly_fields = ("created_at",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "customer_name", "customer_email", "event_type", "event_date",
        "status", "created_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("customer_name", "customer_email", "customer_phone", "event_location")
    readonly_fields = ("reference", "token", "ip_address", "created_at", "updated_at")
    date_hierarchy = "event_date"
    inlines = [QuotationInline, BookingStatusHistoryInline, BookingMessageInline]
    fieldsets = (
        ("Customer", {"fields": ("customer_name", "customer_email", "customer_phone")}),
        ("Event", {"fields": (
            "event_type", "event_date", "event_time",
            "event_location", "guest_count",
            "music_preferences", "additional_requirements",
        )}),
        ("Status", {"fields": ("status", "internal_notes")}),
        ("System", {"fields": ("reference", "token", "ip_address", "created_at", "updated_at")}),
    )


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("booking", "amount", "currency", "expires_at", "created_at")
    search_fields = ("booking__customer_name",)


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("booking", "status", "changed_by", "changed_at")
    list_filter = ("status",)
    readonly_fields = ("changed_at",)


@admin.register(BookingMessage)
class BookingMessageAdmin(admin.ModelAdmin):
    list_display = ("booking", "is_from_dj", "created_at")
    list_filter = ("is_from_dj",)
    readonly_fields = ("created_at",)
