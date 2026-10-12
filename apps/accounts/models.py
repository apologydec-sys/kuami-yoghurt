from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_profile",
    )
    phone_number = models.CharField(max_length=32, blank=True, db_index=True)
    location = models.CharField(max_length=120, blank=True, db_index=True)
    registered_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return f"Profile for {self.user.get_username()}"


class RateLimitBucket(models.Model):
    REGISTRATION = "registration"
    MESSAGE = "message"
    CONVERSATION = "conversation"
    ACTION_CHOICES = [
        (REGISTRATION, "Registration"),
        (MESSAGE, "Message"),
        (CONVERSATION, "Conversation"),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    fingerprint = models.CharField(max_length=64)
    window_started_at = models.DateTimeField(default=timezone.now)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["action", "fingerprint"],
                name="accounts_ratelimit_action_fingerprint_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["action", "window_started_at"],
                name="accounts_rate_window_idx",
            )
        ]


class AdminUserAudit(models.Model):
    USER_VIEW = "user_view"
    CONVERSATION_VIEW = "conversation_view"
    STATUS_CHANGE = "status_change"
    ACTION_CHOICES = [
        (USER_VIEW, "Viewed registered user"),
        (CONVERSATION_VIEW, "Viewed user's conversations"),
        (STATUS_CHANGE, "Changed account status"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="user_management_actions",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="user_management_audit_events",
    )
    action = models.CharField(max_length=24, choices=ACTION_CHOICES)
    detail = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["target", "created_at"],
                name="accounts_audit_target_idx",
            )
        ]
