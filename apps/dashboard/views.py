import datetime
import logging

from cloudinary import CloudinaryResource, uploader
from cloudinary.exceptions import Error as CloudinaryError
from cloudinary.models import CloudinaryField
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from requests.exceptions import RequestException

from apps.bookings.models import Booking, BookingStatusHistory, Quotation
from apps.bookings.utils import generate_whatsapp_link
from apps.chat.models import Conversation, Message as ChatMessage
from apps.core.models import ContactMessage, SiteSettings
from apps.gallery.models import GalleryImage
from apps.music.models import Mix, Track
from apps.videos.models import Video

from .forms import (
    BookingStatusForm,
    GalleryImageForm,
    InternalNoteForm,
    MixForm,
    QuotationForm,
    SiteSettingsForm,
    TrackForm,
    VideoForm,
)

logger = logging.getLogger(__name__)


def staff_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and user.is_staff,
        login_url="/portal/login/",
    )(view_func)


def _cloudinary_resource_id(value):
    if isinstance(value, CloudinaryResource):
        return value.public_id
    return None


def _cleanup_partial_uploads(instance, fields, original_public_ids):
    for field in fields:
        resource = getattr(instance, field.attname)
        public_id = _cloudinary_resource_id(resource)
        if not public_id or public_id == original_public_ids.get(field.name):
            continue
        try:
            uploader.destroy(public_id, resource_type=field.resource_type)
        except (CloudinaryError, RequestException, ValueError) as exc:
            logger.warning(
                "Could not clean up a partial Cloudinary upload for %s (%s).",
                field.name,
                type(exc).__name__,
            )


def _save_cloudinary_form(form, content_type):
    if settings.CLOUDINARY_MISSING_SETTINGS and form.files:
        logger.warning("Rejected %s upload because Cloudinary credentials are missing.", content_type)
        form.add_error(
            None,
            "Cloudinary is not configured. Add CLOUDINARY_URL or all three "
            "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET "
            "values to your local .env file or hosting environment, then retry.",
        )
        return False

    instance = form.instance
    model_fields = [
        field
        for field in instance._meta.fields
        if isinstance(field, CloudinaryField)
    ]
    original_public_ids = {}
    if instance.pk:
        original = instance.__class__._default_manager.get(pk=instance.pk)
        original_public_ids = {
            field.name: _cloudinary_resource_id(getattr(original, field.attname))
            for field in model_fields
        }
    try:
        with transaction.atomic():
            form.save()
    except (CloudinaryError, RequestException, ValueError) as exc:
        _cleanup_partial_uploads(instance, model_fields, original_public_ids)
        logger.warning(
            "Cloudinary upload failed for %s (%s).",
            content_type,
            type(exc).__name__,
        )
        form.add_error(
            None,
            "The upload could not be completed. Check Cloudinary configuration and "
            "connectivity, then try again.",
        )
        return False
    except DatabaseError:
        _cleanup_partial_uploads(instance, model_fields, original_public_ids)
        raise
    return True


class ContentUploadView(View):
    template_name = "dashboard/content_upload_form.html"
    page_title = ""
    back_url = ""
    submit_label = "Upload"

    def render_form(self, request, form):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "page_title": self.page_title,
                "back_url": self.back_url,
                "submit_label": self.submit_label,
                "cloudinary_configured": not settings.CLOUDINARY_MISSING_SETTINGS,
            },
        )


@method_decorator(staff_required, name="dispatch")
class DashboardHomeView(View):
    template_name = "dashboard/home.html"

    def get(self, request):
        today = timezone.now().date()
        context = {
            "bookings_today": Booking.objects.filter(created_at__date=today).count(),
            "pending_bookings": Booking.objects.filter(
                status__in=["received", "under_review", "quotation_sent", "awaiting_response"]
            ).count(),
            "unread_messages": ContactMessage.objects.filter(is_read=False).count(),
            "unread_chats": sum(
                c.unread_count for c in Conversation.objects.all()
            ),
            "total_mix_plays": Mix.objects.aggregate(
                total=__import__("django.db.models", fromlist=["Sum"]).Sum("play_count")
            )["total"] or 0,
            "recent_bookings": Booking.objects.select_related().order_by("-created_at")[:5],
            "recent_messages": ContactMessage.objects.filter(is_read=False).order_by("-created_at")[:5],
        }
        return render(request, self.template_name, context)


@method_decorator(staff_required, name="dispatch")
class BookingListView(View):
    template_name = "dashboard/bookings_list.html"

    def get(self, request):
        qs = Booking.objects.all().order_by("-created_at")

        status_filter = request.GET.get("status", "")
        search = request.GET.get("q", "").strip()
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")

        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                customer_name__icontains=search
            ) | Booking.objects.filter(customer_email__icontains=search)
            qs = qs.order_by("-created_at")
        if date_from:
            try:
                qs = qs.filter(event_date__gte=datetime.date.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                qs = qs.filter(event_date__lte=datetime.date.fromisoformat(date_to))
            except ValueError:
                pass

        from apps.bookings.models import BOOKING_STATUSES
        context = {
            "bookings": qs,
            "booking_statuses": BOOKING_STATUSES,
            "status_filter": status_filter,
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
        }
        return render(request, self.template_name, context)


@method_decorator(staff_required, name="dispatch")
class BookingDetailView(View):
    template_name = "dashboard/booking_detail.html"

    def get(self, request, reference):
        booking = get_object_or_404(Booking, reference=reference)
        quotation = getattr(booking, "quotation", None)
        history = booking.status_history.all()
        context = {
            "booking": booking,
            "quotation": quotation,
            "history": history,
            "quotation_form": QuotationForm(
                initial={
                    "amount": quotation.amount if quotation else "",
                    "currency": quotation.currency if quotation else "GHS",
                    "details": quotation.details if quotation else "",
                    "terms": quotation.terms if quotation else "",
                    "expires_at": quotation.expires_at if quotation else "",
                }
            ),
            "status_form": BookingStatusForm(initial={"status": booking.status}),
            "note_form": InternalNoteForm(initial={"internal_notes": booking.internal_notes}),
        }
        return render(request, self.template_name, context)


@method_decorator(staff_required, name="dispatch")
class QuotationCreateUpdateView(View):
    """Create or update a quotation for a booking."""

    def post(self, request, reference):
        booking = get_object_or_404(Booking, reference=reference)
        form = QuotationForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            quotation, _ = Quotation.objects.update_or_create(
                booking=booking,
                defaults={
                    "amount": cd["amount"],
                    "currency": cd["currency"] or "GHS",
                    "details": cd.get("details", ""),
                    "terms": cd.get("terms", ""),
                    "expires_at": cd.get("expires_at"),
                },
            )
            # Update booking status to quotation_sent if not already past that.
            if booking.status in ("received", "under_review"):
                booking.status = "quotation_sent"
                booking.save(update_fields=["status", "updated_at"])
                BookingStatusHistory.objects.create(
                    booking=booking,
                    status="quotation_sent",
                    changed_by=request.user,
                    note="Quotation created/updated via dashboard.",
                )
            messages.success(request, "Quotation saved successfully.")
        else:
            messages.error(request, "Please correct the errors in the quotation form.")
        return redirect("dashboard:booking_detail", reference=reference)

    def get(self, request, reference):
        return redirect("dashboard:booking_detail", reference=reference)


@method_decorator(staff_required, name="dispatch")
class BookingStatusUpdateView(View):
    """Update booking status and create a history entry."""

    def post(self, request, reference):
        booking = get_object_or_404(Booking, reference=reference)
        form = BookingStatusForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            old_status = booking.status
            new_status = cd["status"]
            booking.status = new_status
            booking.save(update_fields=["status", "updated_at"])
            BookingStatusHistory.objects.create(
                booking=booking,
                status=new_status,
                changed_by=request.user,
                note=cd.get("note", ""),
            )

            # Provide a WhatsApp link for customer notification (non-automated).
            whatsapp_link = None
            if booking.customer_phone:
                msg_text = (
                    f"Hi {booking.customer_name}, your booking (ref: {booking.reference}) "
                    f"status has been updated to: {booking.get_status_display()}. "
                    f"Check your booking at: https://your-domain.com/bookings/booking/{booking.token}/"
                )
                whatsapp_link = generate_whatsapp_link(booking.customer_phone, msg_text)

            messages.success(
                request,
                f"Status updated from {old_status} to {new_status}."
            )
        else:
            messages.error(request, "Invalid status update.")
        return redirect("dashboard:booking_detail", reference=reference)

    def get(self, request, reference):
        return redirect("dashboard:booking_detail", reference=reference)


@method_decorator(staff_required, name="dispatch")
class InternalNoteUpdateView(View):
    """Update internal notes on a booking."""

    def post(self, request, reference):
        booking = get_object_or_404(Booking, reference=reference)
        form = InternalNoteForm(request.POST)
        if form.is_valid():
            booking.internal_notes = form.cleaned_data["internal_notes"]
            booking.save(update_fields=["internal_notes", "updated_at"])
            messages.success(request, "Internal notes saved.")
        else:
            messages.error(request, "Could not save notes.")
        return redirect("dashboard:booking_detail", reference=reference)

    def get(self, request, reference):
        return redirect("dashboard:booking_detail", reference=reference)


@method_decorator(staff_required, name="dispatch")
class ContactMessageListView(View):
    template_name = "dashboard/messages_list.html"

    def get(self, request):
        if request.GET.get("mark_all_read"):
            ContactMessage.objects.filter(is_read=False).update(is_read=True)
            messages.success(request, "All messages marked as read.")
            return redirect("dashboard:messages")

        msgs = ContactMessage.objects.all().order_by("-created_at")
        return render(request, self.template_name, {"contact_messages": msgs})


@method_decorator(staff_required, name="dispatch")
class GalleryManageView(View):
    template_name = "dashboard/gallery_manage.html"

    def get(self, request):
        images = GalleryImage.objects.select_related("category").order_by("order", "-created_at")
        return render(request, self.template_name, {"images": images})


@method_decorator(staff_required, name="dispatch")
class GalleryUploadView(ContentUploadView):
    page_title = "Upload Gallery Image"
    back_url = "portal:gallery"
    submit_label = "Upload image"

    def get(self, request):
        return self.render_form(request, GalleryImageForm())

    def post(self, request):
        form = GalleryImageForm(request.POST, request.FILES)
        if form.is_valid():
            if not _save_cloudinary_form(form, "gallery image"):
                return self.render_form(request, form)
            messages.success(request, "Image uploaded successfully.")
            return redirect("dashboard:gallery")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class GalleryDeleteView(View):
    def post(self, request, pk):
        image = get_object_or_404(GalleryImage, pk=pk)
        image.delete()
        messages.success(request, "Image deleted.")
        return redirect("dashboard:gallery")

    def get(self, request, pk):
        return redirect("dashboard:gallery")


@method_decorator(staff_required, name="dispatch")
class MusicManageView(View):
    template_name = "dashboard/music_manage.html"

    def get(self, request):
        mixes = Mix.objects.select_related("category").order_by("-created_at")
        tracks = Track.objects.select_related("category", "mix").order_by("-created_at")
        return render(request, self.template_name, {"mixes": mixes, "tracks": tracks})


@method_decorator(staff_required, name="dispatch")
class MixAddView(ContentUploadView):
    page_title = "Add Music Mix"
    back_url = "portal:music"
    submit_label = "Add mix"

    def get(self, request):
        return self.render_form(request, MixForm())

    def post(self, request):
        form = MixForm(request.POST, request.FILES)
        if form.is_valid():
            if not _save_cloudinary_form(form, "music mix"):
                return self.render_form(request, form)
            messages.success(request, "Mix added successfully.")
            return redirect("dashboard:music")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class MixEditView(ContentUploadView):
    page_title = "Edit Music Mix"
    back_url = "portal:music"
    submit_label = "Save changes"

    def get(self, request, slug):
        mix = get_object_or_404(Mix, slug=slug)
        form = MixForm(instance=mix)
        return self.render_form(request, form)

    def post(self, request, slug):
        mix = get_object_or_404(Mix, slug=slug)
        form = MixForm(request.POST, request.FILES, instance=mix)
        if form.is_valid():
            if not _save_cloudinary_form(form, "music mix"):
                return self.render_form(request, form)
            messages.success(request, "Mix updated successfully.")
            return redirect("dashboard:music")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class TrackAddView(ContentUploadView):
    page_title = "Add Music Track"
    back_url = "portal:music"
    submit_label = "Add track"

    def get(self, request):
        return self.render_form(request, TrackForm())

    def post(self, request):
        form = TrackForm(request.POST, request.FILES)
        if form.is_valid():
            if not _save_cloudinary_form(form, "music track"):
                return self.render_form(request, form)
            messages.success(request, "Track added successfully.")
            return redirect("dashboard:music")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class VideoManageView(View):
    template_name = "dashboard/videos_manage.html"

    def get(self, request):
        videos = Video.objects.select_related("category").order_by("-created_at")
        return render(request, self.template_name, {"videos": videos})


@method_decorator(staff_required, name="dispatch")
class VideoAddView(ContentUploadView):
    page_title = "Add Video"
    back_url = "portal:videos"
    submit_label = "Add video"

    def get(self, request):
        return self.render_form(request, VideoForm())

    def post(self, request):
        form = VideoForm(request.POST, request.FILES)
        if form.is_valid():
            if not _save_cloudinary_form(form, "video"):
                return self.render_form(request, form)
            messages.success(request, "Video added successfully.")
            return redirect("dashboard:videos")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class ChatAdminListView(View):
    template_name = "dashboard/chat_list.html"

    def get(self, request):
        conversations = Conversation.objects.prefetch_related("chat_messages").order_by("-updated_at")
        return render(request, self.template_name, {"conversations": conversations})


@method_decorator(staff_required, name="dispatch")
class ChatAdminReplyView(View):
    template_name = "dashboard/chat_reply.html"

    def get(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        # Mark all customer messages as read when admin views the conversation.
        conversation.chat_messages.filter(is_from_dj=False, is_read=False).update(is_read=True)
        chat_messages = conversation.chat_messages.all()
        from apps.chat.forms import MessageForm
        form = MessageForm()
        return render(
            request,
            self.template_name,
            {"conversation": conversation, "chat_messages": chat_messages, "form": form},
        )

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        from apps.chat.forms import MessageForm
        form = MessageForm(request.POST)
        if form.is_valid():
            ChatMessage.objects.create(
                conversation=conversation,
                content=form.cleaned_data["content"],
                is_from_dj=True,
                is_read=True,
            )
            conversation.save(update_fields=["updated_at"])
            messages.success(request, "Reply sent.")
            return redirect("dashboard:chat_reply", pk=pk)
        chat_messages = conversation.chat_messages.all()
        return render(
            request,
            self.template_name,
            {"conversation": conversation, "chat_messages": chat_messages, "form": form},
        )


@method_decorator(staff_required, name="dispatch")
class SiteSettingsView(View):
    template_name = "dashboard/site_settings.html"

    def get(self, request):
        settings_obj = SiteSettings.get_settings()
        current_profile_image = settings_obj.profile_image
        form = SiteSettingsForm(instance=settings_obj)
        return render(
            request,
            self.template_name,
            {
                "settings": settings_obj,
                "form": form,
                "current_profile_image": current_profile_image,
                "cloudinary_configured": not settings.CLOUDINARY_MISSING_SETTINGS,
            },
        )

    def post(self, request):
        settings_obj = SiteSettings.get_settings()
        current_profile_image = settings_obj.profile_image
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            if not _save_cloudinary_form(form, "site profile image"):
                return render(
                    request,
                    self.template_name,
                    {
                        "settings": settings_obj,
                        "form": form,
                        "current_profile_image": current_profile_image,
                        "cloudinary_configured": not settings.CLOUDINARY_MISSING_SETTINGS,
                    },
                )
            messages.success(request, "Site settings saved.")
            return redirect("dashboard:site_settings")
        return render(
            request,
            self.template_name,
            {
                "settings": settings_obj,
                "form": form,
                "current_profile_image": current_profile_image,
                "cloudinary_configured": not settings.CLOUDINARY_MISSING_SETTINGS,
            },
        )
