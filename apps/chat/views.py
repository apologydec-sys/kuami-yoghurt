from datetime import timedelta
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from apps.accounts.models import UserProfile
from apps.accounts.services import conversation_allowed, message_allowed

from .forms import MessageForm, StartConversationForm
from .models import Conversation, Message

MESSAGE_PAGE_SIZE = 50
POLL_PAGE_SIZE = 100
AGENT_ONLINE_WINDOW = timedelta(minutes=2)


def _owned_conversation(request, pk):
    return get_object_or_404(
        Conversation.objects.filter(user=request.user),
        pk=pk,
    )


def _serialize_message(message, user):
    is_deleted = message.deleted_at is not None
    return {
        "id": message.pk,
        "content": "" if is_deleted else message.content,
        "timestamp": message.created_at.isoformat(),
        "is_from_dj": message.is_from_dj,
        "is_own": message.sender_id == user.pk,
        "is_deleted": is_deleted,
    }


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class ChatStartView(View):
    template_name = "chat/start.html"

    def get(self, request):
        return render(request, self.template_name, {"form": StartConversationForm()})

    def post(self, request):
        form = StartConversationForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        if not conversation_allowed(request.user.pk):
            form.add_error(
                None,
                "You have started several conversations recently. Please use My Chats or try again later.",
            )
            return render(request, self.template_name, {"form": form}, status=429)

        profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={"registered_at": request.user.date_joined},
        )
        customer_name = request.user.get_full_name().strip() or request.user.get_username()
        with transaction.atomic():
            conversation = Conversation.objects.create(
                session_key=f"account-{request.user.pk}-{uuid.uuid4().hex}",
                user=request.user,
                customer_name=customer_name,
                customer_email=request.user.email,
                customer_phone=profile.phone_number,
                customer_last_seen=timezone.now(),
            )
            Message.objects.create(
                conversation=conversation,
                content=form.cleaned_data["initial_message"],
                is_from_dj=False,
                sender=request.user,
            )
        conversation.save(update_fields=["updated_at"])
        return redirect("chat:window", pk=conversation.pk)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class ChatWindowView(View):
    template_name = "chat/window.html"

    def get(self, request, pk):
        conversation = _owned_conversation(request, pk)
        now = timezone.now()
        conversation.customer_last_seen = now
        conversation.save(update_fields=["customer_last_seen"])
        conversation.chat_messages.filter(
            is_from_dj=True,
            is_read=False,
            deleted_at__isnull=True,
        ).update(is_read=True)

        newest_first = list(
            conversation.chat_messages.order_by("-pk")[:MESSAGE_PAGE_SIZE]
        )
        messages_for_page = list(reversed(newest_first))
        first_id = messages_for_page[0].pk if messages_for_page else None
        has_older_messages = bool(
            first_id
            and conversation.chat_messages.filter(pk__lt=first_id).exists()
        )
        return render(
            request,
            self.template_name,
            {
                "conversation": conversation,
                "messages": messages_for_page,
                "form": MessageForm(),
                "has_older_messages": has_older_messages,
            },
        )


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class SendMessageView(View):
    def post(self, request, pk):
        conversation = _owned_conversation(request, pk)
        form = MessageForm(request.POST)
        if not form.is_valid():
            return JsonResponse(
                {
                    "error": "Validation failed",
                    "fields": {
                        name: errors[0] for name, errors in form.errors.items()
                    },
                },
                status=400,
            )
        if not message_allowed(request.user.pk, conversation.pk):
            return JsonResponse(
                {"error": "Message limit reached. Please wait before sending more messages."},
                status=429,
            )

        now = timezone.now()
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                content=form.cleaned_data["content"],
                is_from_dj=False,
                sender=request.user,
            )
            Conversation.objects.filter(pk=conversation.pk).update(
                updated_at=now,
                customer_last_seen=now,
            )
        return JsonResponse(_serialize_message(message, request.user))

    def get(self, request, pk):
        return JsonResponse({"error": "Method not allowed"}, status=405)


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class PollMessagesView(View):
    def get(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        now = timezone.now()
        is_customer = conversation.user_id == request.user.pk
        if not is_customer and not request.user.is_staff:
            raise Http404

        if is_customer:
            Conversation.objects.filter(pk=pk).update(customer_last_seen=now)
            conversation.chat_messages.filter(
                is_from_dj=True,
                is_read=False,
                deleted_at__isnull=True,
            ).update(is_read=True)
        else:
            Conversation.objects.filter(pk=pk).update(staff_last_seen=now)
            conversation.chat_messages.filter(
                is_from_dj=False,
                is_read=False,
                deleted_at__isnull=True,
            ).update(is_read=True)

        after_param = request.GET.get("after", "0")
        if not after_param.isdecimal():
            return JsonResponse({"error": "Invalid message cursor."}, status=400)
        queryset = conversation.chat_messages.filter(pk__gt=int(after_param)).order_by("pk")
        fetched = list(queryset[:POLL_PAGE_SIZE + 1])
        has_more = len(fetched) > POLL_PAGE_SIZE
        data = [
            _serialize_message(message, request.user)
            for message in fetched[:POLL_PAGE_SIZE]
        ]
        deleted_updates = [
            _serialize_message(message, request.user)
            for message in conversation.chat_messages.filter(
                deleted_at__gte=now - timedelta(minutes=2)
            ).order_by("pk")[:POLL_PAGE_SIZE]
        ]
        agent_last_seen = conversation.staff_last_seen
        agent_online = bool(
            is_customer
            and agent_last_seen
            and agent_last_seen >= now - AGENT_ONLINE_WINDOW
        )
        customer_last_seen = conversation.customer_last_seen
        customer_online = bool(
            not is_customer
            and customer_last_seen
            and customer_last_seen >= now - AGENT_ONLINE_WINDOW
        )
        return JsonResponse(
            {
                "messages": data,
                "deleted_updates": deleted_updates,
                "has_more": has_more,
                "agent_online": agent_online,
                "customer_online": customer_online,
            }
        )


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class MessageHistoryView(View):
    def get(self, request, pk):
        conversation = _owned_conversation(request, pk)
        before = request.GET.get("before", "")
        if not before.isdecimal():
            return JsonResponse({"error": "Invalid message cursor."}, status=400)
        queryset = conversation.chat_messages.filter(pk__lt=int(before)).order_by("-pk")
        fetched = list(queryset[:MESSAGE_PAGE_SIZE + 1])
        has_more = len(fetched) > MESSAGE_PAGE_SIZE
        messages_page = list(reversed(fetched[:MESSAGE_PAGE_SIZE]))
        return JsonResponse(
            {
                "messages": [
                    _serialize_message(message, request.user)
                    for message in messages_page
                ],
                "has_more": has_more,
            }
        )


@method_decorator(login_required(login_url="/accounts/login/"), name="dispatch")
class DeleteOwnMessageView(View):
    def post(self, request, pk, message_pk):
        conversation = _owned_conversation(request, pk)
        message = get_object_or_404(
            Message.objects.filter(
                conversation=conversation,
                sender=request.user,
                deleted_at__isnull=True,
            ),
            pk=message_pk,
        )
        if request.POST.get("confirm_delete") != "1":
            messages.error(request, "Confirm message deletion before continuing.")
            return redirect("chat:window", pk=conversation.pk)
        message.deleted_at = timezone.now()
        message.deleted_by = request.user
        message.deletion_kind = "owner"
        message.save(
            update_fields=["deleted_at", "deleted_by", "deletion_kind"]
        )
        Conversation.objects.filter(pk=conversation.pk).update(
            updated_at=timezone.now()
        )
        messages.success(request, "Your message was removed from the conversation.")
        return redirect("chat:window", pk=conversation.pk)
