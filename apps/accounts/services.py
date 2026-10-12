import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import RateLimitBucket


def rate_limit_fingerprint(action, identity):
    value = f"{action}:{identity}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value,
        hashlib.sha256,
    ).hexdigest()


def consume_rate_limit(action, identity, *, limit, window):
    fingerprint = rate_limit_fingerprint(action, identity)
    now = timezone.now()
    with transaction.atomic():
        bucket, _ = RateLimitBucket.objects.select_for_update().get_or_create(
            action=action,
            fingerprint=fingerprint,
        )
        if bucket.window_started_at <= now - window:
            bucket.window_started_at = now
            bucket.count = 0
        if bucket.count >= limit:
            return False
        bucket.count += 1
        bucket.save(update_fields=["window_started_at", "count"])
    return True


def registration_allowed(remote_addr):
    return consume_rate_limit(
        RateLimitBucket.REGISTRATION,
        remote_addr or "unknown",
        limit=5,
        window=timedelta(hours=1),
    )


def message_allowed(user_id, conversation_id):
    return consume_rate_limit(
        RateLimitBucket.MESSAGE,
        f"{user_id}:{conversation_id}",
        limit=30,
        window=timedelta(hours=1),
    )


def conversation_allowed(user_id):
    return consume_rate_limit(
        RateLimitBucket.CONVERSATION,
        str(user_id),
        limit=5,
        window=timedelta(hours=1),
    )
