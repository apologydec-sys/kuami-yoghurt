from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, OuterRef, Subquery
from django.shortcuts import redirect, render
from django.views import View

from apps.chat.models import Conversation, Message

from .forms import AccountAuthenticationForm, ProfileForm, RegistrationForm
from .models import UserProfile
from .services import registration_allowed


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = AccountAuthenticationForm
    redirect_authenticated_user = True


class RegistrationView(View):
    template_name = "accounts/register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:my_chats")
        return render(request, self.template_name, {"form": RegistrationForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:my_chats")
        form = RegistrationForm(request.POST)
        if not registration_allowed(request.META.get("REMOTE_ADDR")):
            form.add_error(None, "Registration limit reached. Please try again later.")
            return render(request, self.template_name, {"form": form}, status=429)
        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                if get_user_model().objects.filter(
                    username=form.cleaned_data["username"]
                ).exists():
                    form.add_error("username", "That username is already in use.")
                else:
                    raise
            else:
                login(request, user)
                messages.success(request, "Your account is ready. You can now chat with DJ Kuami Yoghurt.")
                return redirect("accounts:my_chats")
        return render(request, self.template_name, {"form": form})


class ProfileView(View):
    template_name = "accounts/profile.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": ProfileForm(
                    user=request.user,
                    instance=UserProfile.objects.get_or_create(
                        user=request.user,
                        defaults={"registered_at": request.user.date_joined},
                    )[0],
                )
            },
        )

    def post(self, request):
        form = ProfileForm(
            request.POST,
            user=request.user,
            instance=UserProfile.objects.get_or_create(
                user=request.user,
                defaults={"registered_at": request.user.date_joined},
            )[0],
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Your account details have been updated.")
            return redirect("accounts:profile")
        return render(request, self.template_name, {"form": form})


class MyChatsView(View):
    template_name = "accounts/my_chats.html"

    def get(self, request):
        conversations = (
            Conversation.objects.filter(user=request.user)
            .annotate(message_count=Count("chat_messages"))
            .annotate(
                latest_preview=Subquery(
                    Message.objects.filter(
                        conversation_id=OuterRef("pk"),
                        deleted_at__isnull=True,
                    )
                    .order_by("-pk")
                    .values("content")[:1]
                )
            )
            .order_by("-updated_at")
        )
        page_obj = Paginator(conversations, 20).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {"page_obj": page_obj, "conversations": page_obj.object_list},
        )
