from django.db import models
from django.conf import settings


class Conversation(models.Model):
    session_key = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=30, blank=True, null=True)
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_conversations",
    )
    customer_last_seen = models.DateTimeField(null=True, blank=True)
    staff_last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["user", "-updated_at"],
                name="chat_user_updated_idx",
            ),
            models.Index(
                fields=["-updated_at", "id"],
                name="chat_updated_id_idx",
            ),
        ]
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"

    def __str__(self):
        return f"Conversation with {self.customer_name} ({self.session_key[:10]}…)"

    @property
    def unread_count(self):
        return self.chat_messages.filter(
            is_from_dj=False,
            is_read=False,
            deleted_at__isnull=True,
        ).count()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="chat_messages"
    )
    content = models.TextField(max_length=2000)
    is_from_dj = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages_sent",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages_deleted",
    )
    deletion_kind = models.CharField(
        max_length=16,
        choices=[("owner", "Sender deletion"), ("moderation", "Staff moderation")],
        blank=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["conversation", "id"],
                name="chat_message_cursor_idx",
            ),
            models.Index(
                fields=["conversation", "deleted_at"],
                name="chat_deleted_poll_idx",
            ),
        ]
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        if self.deleted_at:
            return "Deleted message"
        sender = "DJ" if self.is_from_dj else self.conversation.customer_name
        return f"{sender}: {self.content[:60]}"


class MessageModerationAction(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.PROTECT,
        related_name="moderation_actions",
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_moderation_actions",
    )
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
