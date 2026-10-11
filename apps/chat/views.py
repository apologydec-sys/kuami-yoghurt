import json
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote_plus

from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_tz
from django.views import View

from .forms import MessageForm, StartConversationForm
from .models import Conversation, Message

_RATE_LIMIT_WINDOW_HOURS = 1
_RATE_LIMIT_MAX_MESSAGES = 20


def _ensure_session(request):
    """Make sure there's a session key available."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


class ChatStartView(View):
    template_name = "chat/start.html"

    def get(self, request):
        form = StartConversationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = StartConversationForm(request.POST)
        if form.is_valid():
            session_key = _ensure_session(request)
            cd = form.cleaned_data

            # Re-use existing conversation for this session to avoid duplicates.
            conversation, created = Conversation.objects.get_or_create(
                session_key=session_key,
                defaults={
                    "customer_name": cd["customer_name"],
                    "customer_email": cd["customer_email"],
                    "customer_phone": cd.get("customer_phone", "") or "",
                },
            )

            if not created:
                # Update contact details in case they changed.
                conversation.customer_name = cd["customer_name"]
                conversation.customer_email = cd["customer_email"]
                conversation.customer_phone = cd.get("customer_phone", "") or ""
                conversation.save(
                    update_fields=["customer_name", "customer_email", "customer_phone", "updated_at"]
                )

            # Save the opening message.
            Message.objects.create(
                conversation=conversation,
                content=cd["initial_message"],
                is_from_dj=False,
            )

            request.session["chat_conversation_id"] = conversation.pk
            return redirect("chat:window", pk=conversation.pk)

        return render(request, self.template_name, {"form": form})


class ChatWindowView(View):
    template_name = "chat/window.html"

    def get(self, request, pk):
        session_key = _ensure_session(request)
        conversation = get_object_or_404(Conversation, pk=pk)

        # Enforce ownership — session must match.
        if conversation.session_key != session_key:
            return HttpResponseForbidden("You do not have access to this conversation.")

        # Mark all DJ messages as read.
        conversation.chat_messages.filter(is_from_dj=True, is_read=False).update(is_read=True)

        messages = conversation.chat_messages.all()
        form = MessageForm()
        return render(
            request,
            self.template_name,
            {
                "conversation": conversation,
                "messages": messages,
                "form": form,
            },
        )


class SendMessageView(View):
    """POST-only AJAX endpoint for sending a customer message."""

    def post(self, request, pk):
        session_key = _ensure_session(request)
        conversation = get_object_or_404(Conversation, pk=pk)

        if conversation.session_key != session_key:
            return JsonResponse({"error": "Forbidden"}, status=403)

        # Rate limiting: max 20 messages per hour from this conversation.
        one_hour_ago = django_tz.now() - timedelta(hours=_RATE_LIMIT_WINDOW_HOURS)
        recent_count = conversation.chat_messages.filter(
            is_from_dj=False, created_at__gte=one_hour_ago
        ).count()
        if recent_count >= _RATE_LIMIT_MAX_MESSAGES:
            return JsonResponse(
                {"error": "Message limit reached. Please wait before sending more messages."},
                status=429,
            )

        form = MessageForm(request.POST)
        if not form.is_valid():
            errors = {k: v[0] for k, v in form.errors.items()}
            return JsonResponse({"error": "Validation failed", "fields": errors}, status=400)

        msg = Message.objects.create(
            conversation=conversation,
            content=form.cleaned_data["content"],
            is_from_dj=False,
        )
        conversation.save(update_fields=["updated_at"])

        return JsonResponse(
            {
                "id": msg.pk,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "is_from_dj": msg.is_from_dj,
            }
        )

    def get(self, request, pk):
        return JsonResponse({"error": "Method not allowed"}, status=405)


class PollMessagesView(View):
    """GET AJAX endpoint — returns messages created after ?since= timestamp."""

    def get(self, request, pk):
        session_key = _ensure_session(request)
        conversation = get_object_or_404(Conversation, pk=pk)

        if conversation.session_key != session_key:
            return JsonResponse({"error": "Forbidden"}, status=403)

        since_param = request.GET.get("since", "")
        qs = conversation.chat_messages.all()

        if since_param:
            try:
                normalized = unquote_plus(since_param).replace(" ", "+")
                since_dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
                qs = qs.filter(created_at__gt=since_dt)
            except (ValueError, TypeError):
                pass  # Ignore invalid timestamps — return all messages.

        # Mark incoming DJ messages as read when the customer polls.
        conversation.chat_messages.filter(is_from_dj=True, is_read=False).update(is_read=True)

        data = [
            {
                "id": m.pk,
                "content": m.content,
                "timestamp": m.created_at.isoformat(),
                "is_from_dj": m.is_from_dj,
            }
            for m in qs
        ]
        return JsonResponse({"messages": data})
