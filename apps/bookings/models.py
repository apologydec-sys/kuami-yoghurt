import secrets
import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


EVENT_TYPES = [
    ("wedding", "Wedding"),
    ("birthday", "Birthday Party"),
    ("private_party", "Private Party"),
    ("school", "School Event"),
    ("festival", "Festival / Concert"),
    ("corporate", "Corporate Event"),
    ("funeral", "Funeral"),
    ("club", "Club / Nightlife"),
    ("other", "Other"),
]

BOOKING_STATUSES = [
    ("received", "Received"),
    ("under_review", "Under Review"),
    ("quotation_sent", "Quotation Sent"),
    ("awaiting_response", "Awaiting Customer Response"),
    ("confirmed", "Confirmed"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("declined", "Declined"),
    ("cancelled", "Cancelled"),
]


def _generate_token():
    return secrets.token_urlsafe(48)


class Booking(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    token = models.CharField(
        max_length=100,
        unique=True,
        default=_generate_token,
        editable=False,
        db_index=True,
    )
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_date = models.DateField()
    event_time = models.TimeField(null=True, blank=True)
    event_location = models.CharField(max_length=500)
    guest_count = models.PositiveIntegerField(null=True, blank=True)
    music_preferences = models.TextField(blank=True)
    additional_requirements = models.TextField(blank=True)
    status = models.CharField(
        max_length=30, choices=BOOKING_STATUSES, default="received"
    )
    internal_notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"

    def __str__(self):
        return f"{self.customer_name} — {self.get_event_type_display()} ({self.reference})"


class Quotation(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="quotation"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="GHS")
    details = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Quotation"
        verbose_name_plural = "Quotations"

    def __str__(self):
        return f"Quotation for {self.booking.customer_name} — {self.currency} {self.amount}"


class BookingStatusHistory(models.Model):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="status_history"
    )
    status = models.CharField(max_length=30, choices=BOOKING_STATUSES)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_status_changes",
    )
    note = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Booking Status History"
        verbose_name_plural = "Booking Status Histories"

    def __str__(self):
        return f"{self.booking.reference} → {self.status} at {self.changed_at}"


class BookingMessage(models.Model):
    """Customer-visible updates attached to a booking."""

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="messages"
    )
    message = models.TextField()
    is_from_dj = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Booking Message"
        verbose_name_plural = "Booking Messages"

    def __str__(self):
        sender = "DJ" if self.is_from_dj else self.booking.customer_name
        return f"{sender}: {self.message[:60]}"
