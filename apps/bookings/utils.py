import secrets
from urllib.parse import quote


def generate_booking_token() -> str:
    """Return a cryptographically secure URL-safe token (48 bytes = 64 chars)."""
    return secrets.token_urlsafe(48)


def get_client_ip(request) -> str | None:
    """Extract the real client IP from a Django request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def generate_whatsapp_link(phone: str, message: str) -> str:
    """Return a wa.me deep-link with a URL-encoded pre-filled message.

    Strips all non-digit characters from the phone number except a leading '+'.
    """
    # Normalise the phone number: keep digits and an optional leading '+'.
    cleaned = "".join(c for c in phone.strip() if c.isdigit() or c == "+")
    # Remove '+' for the wa.me URL format (it expects the international number).
    cleaned = cleaned.lstrip("+")
    encoded_message = quote(message, safe="")
    return f"https://wa.me/{cleaned}?text={encoded_message}"
