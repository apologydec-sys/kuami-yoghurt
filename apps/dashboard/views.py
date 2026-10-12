import datetime
import logging

from cloudinary import CloudinaryResource, uploader
from cloudinary.exceptions import Error as CloudinaryError
from cloudinary.models import CloudinaryField
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from requests.exceptions import RequestException
from django.db.models.fields.files import FileField

from apps.bookings.models import Booking, BookingStatusHistory, Quotation
from apps.bookings.utils import generate_whatsapp_link
from apps.chat.models import Conversation, Message as ChatMessage
from apps.core.models import Biography, ContactMessage, SiteSettings
from apps.gallery.models import GalleryCategory, GalleryImage
from apps.music.models import Category, Mix, Track
from apps.videos.models import Video, VideoCategory

from .forms import (
    BookingStatusForm,
    BiographyForm,
    GalleryCategoryForm,
    GalleryImageForm,
    InternalNoteForm,
    MusicCategoryForm,
    MixForm,
    QuotationForm,
    SiteSettingsForm,
    TrackForm,
    VideoCategoryForm,
    VideoForm,
)

logger = logging.getLogger(__name__)


def staff_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and user.is_staff,
        login_url="/portal/login/",
    )(view_func)


def superuser_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and user.is_staff and user.is_superuser,
        login_url="/portal/login/",
    )(view_func)


def _media_name(value):
    if not value:
        return ""
    return (
        getattr(value, "name", None)
        or getattr(value, "public_id", None)
        or str(value)
    )


def _is_media_field(field):
    return isinstance(field, (FileField, CloudinaryField))


def _instance_media(instance):
    return [
        (field, _media_name(field.value_from_object(instance)))
        for field in instance._meta.fields
        if _is_media_field(field)
        and _media_name(field.value_from_object(instance))
    ]


def _same_storage(first, second):
    if first.__class__ is not second.__class__:
        return False
    if isinstance(first, CloudinaryField) or isinstance(second, CloudinaryField):
        return getattr(first, "resource_type", "image") == getattr(
            second, "resource_type", "image"
        )
    return True


def _media_is_referenced(storage_field, name, deleted_instance):
    for model in apps.get_models():
        for field in model._meta.fields:
            if not _is_media_field(field) or not _same_storage(field, storage_field):
                continue
            queryset = model._base_manager.filter(**{field.name: name})
            if model is deleted_instance.__class__:
                queryset = queryset.exclude(pk=deleted_instance.pk)
            if queryset.exists():
                return True
    return False


def _delete_media_files(media_files, instance):
    failures = []
    for field, name in media_files:
        if _media_is_referenced(field, name, instance):
            continue
        try:
            if isinstance(field, CloudinaryField):
                result = uploader.destroy(name, resource_type=field.resource_type)
                if result.get("result") not in {"ok", "not found"}:
                    failures.append(field.name)
            else:
                field.storage.delete(name)
        except (CloudinaryError, RequestException, OSError, ValueError) as exc:
            logger.warning(
                "Media cleanup failed for %s (%s).",
                field.name,
                type(exc).__name__,
            )
            failures.append(field.name)
    return failures


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


class ContentDetailView(View):
    model = None
    lookup_field = "pk"
    lookup_url_kwarg = "pk"
    field_names = ()
    edit_url_name = ""
    delete_url_name = ""
    publish_url_name = ""
    list_url_name = ""
    template_name = "dashboard/content_detail.html"

    def get(self, request, **kwargs):
        obj = get_object_or_404(
            self.model,
            **{
                self.lookup_field: kwargs.get(self.lookup_url_kwarg),
            },
        )
        details = []
        for name in self.field_names:
            field = self.model._meta.get_field(name)
            value = getattr(obj, name)
            if _is_media_field(field):
                value = _media_name(value) or "Not set"
            elif value is None or value == "":
                value = "—"
            elif name == "category":
                value = value.name if value else "—"
            details.append((field.verbose_name.title(), value))
        identity_kwargs = {self.lookup_url_kwarg: getattr(obj, self.lookup_field)}
        context = {
            "object": obj,
            "details": details,
            "list_url": reverse(self.list_url_name),
            "edit_url": reverse(self.edit_url_name, kwargs=identity_kwargs),
            "delete_url": reverse(self.delete_url_name, kwargs=identity_kwargs),
            "publish_url": (
                reverse(self.publish_url_name, kwargs=identity_kwargs)
                if self.publish_url_name and hasattr(obj, "is_published")
                else None
            ),
        }
        return render(request, self.template_name, context)


class ContentDeleteView(View):
    model = None
    lookup_field = "pk"
    lookup_url_kwarg = "pk"
    list_url_name = ""
    template_name = "dashboard/content_confirm_delete.html"
    success_message = "Item deleted."

    def get_object(self, kwargs):
        return get_object_or_404(
            self.model,
            **{self.lookup_field: kwargs.get(self.lookup_url_kwarg)},
        )

    def get(self, request, **kwargs):
        obj = self.get_object(kwargs)
        return render(
            request,
            self.template_name,
            {
                "object": obj,
                "list_url": reverse(self.list_url_name),
                "related_warning": self.get_related_warning(obj),
            },
        )

    def get_related_warning(self, obj):
        return ""

    def post(self, request, **kwargs):
        obj = self.get_object(kwargs)
        if request.POST.get("confirm_delete") != "1":
            messages.error(request, "Confirm the deletion using the button below.")
            return redirect(
                request.path
            )
        media_files = _instance_media(obj)
        try:
            with transaction.atomic():
                obj.delete()
        except (ProtectedError, IntegrityError):
            logger.info("Blocked deletion of referenced %s.", self.model.__name__)
            messages.error(
                request,
                "This item is still referenced and cannot be deleted. Remove or reassign "
                "those references first.",
            )
            return redirect(self.list_url_name)
        except DatabaseError:
            logger.exception("Database error while deleting %s.", self.model.__name__)
            messages.error(request, "The item could not be deleted. Please try again.")
            return redirect(self.list_url_name)

        cleanup_failures = _delete_media_files(media_files, obj)
        if cleanup_failures:
            logger.error(
                "Deleted %s record but could not remove all associated media files.",
                self.model.__name__,
            )
            messages.warning(
                request,
                "The item was deleted, but one or more media files could not be removed. "
                "An administrator should review Cloudinary or storage cleanup.",
            )
        else:
            messages.success(request, self.success_message)
        return redirect(self.list_url_name)


class ContentPublishView(View):
    model = None
    lookup_field = "pk"
    lookup_url_kwarg = "pk"
    list_url_name = ""

    def get(self, request, **kwargs):
        return HttpResponseNotAllowed(["POST"])

    def post(self, request, **kwargs):
        obj = get_object_or_404(
            self.model,
            **{self.lookup_field: kwargs.get(self.lookup_url_kwarg)},
        )
        obj.is_published = not obj.is_published
        obj.save(update_fields=["is_published", "updated_at"])
        state = "published" if obj.is_published else "unpublished"
        messages.success(request, f"{obj} was {state}.")
        return redirect(self.list_url_name)


class CategoryFormView(View):
    model = None
    form_class = None
    page_title = ""
    list_url_name = "portal:categories"
    template_name = "dashboard/category_form.html"
    lookup_field = "pk"
    lookup_url_kwarg = "pk"
    action = "Add"

    def get(self, request, **kwargs):
        instance = None
        if self.lookup_url_kwarg in kwargs:
            instance = get_object_or_404(
                self.model,
                **{self.lookup_field: kwargs[self.lookup_url_kwarg]},
            )
        return render(
            request,
            self.template_name,
            {
                "form": self.form_class(instance=instance),
                "page_title": self.page_title,
                "action": self.action,
                "list_url": reverse(self.list_url_name),
            },
        )

    def post(self, request, **kwargs):
        instance = None
        if self.lookup_url_kwarg in kwargs:
            instance = get_object_or_404(
                self.model,
                **{self.lookup_field: kwargs[self.lookup_url_kwarg]},
            )
        form = self.form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"{self.page_title} saved successfully.")
            return redirect(self.list_url_name)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "page_title": self.page_title,
                "action": self.action,
                "list_url": reverse(self.list_url_name),
            },
        )


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
        queryset = GalleryImage.objects.select_related("category").order_by(
            "order", "-created_at"
        )
        search = request.GET.get("q", "").strip()
        publication = request.GET.get("publication", "")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        if publication in {"published", "draft"}:
            queryset = queryset.filter(is_published=publication == "published")
        page_obj = Paginator(queryset, 24).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {
                "images": page_obj.object_list,
                "page_obj": page_obj,
                "image_count": queryset.count(),
                "cloudinary_configured": not settings.CLOUDINARY_MISSING_SETTINGS,
                "search_query": search,
                "publication_filter": publication,
            },
        )


@method_decorator(superuser_required, name="dispatch")
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


@method_decorator(superuser_required, name="dispatch")
class GalleryEditView(ContentUploadView):
    page_title = "Edit Gallery Image"
    back_url = "portal:gallery"
    submit_label = "Save changes"

    def get(self, request, pk):
        image = get_object_or_404(GalleryImage, pk=pk)
        return self.render_form(request, GalleryImageForm(instance=image))

    def post(self, request, pk):
        image = get_object_or_404(GalleryImage, pk=pk)
        form = GalleryImageForm(request.POST, request.FILES, instance=image)
        if form.is_valid():
            if not _save_cloudinary_form(form, "gallery image"):
                return self.render_form(request, form)
            messages.success(request, "Gallery image updated successfully.")
            return redirect("portal:gallery")
        return self.render_form(request, form)


@method_decorator(superuser_required, name="dispatch")
class GalleryDeleteView(ContentDeleteView):
    model = GalleryImage
    list_url_name = "portal:gallery"
    success_message = "Gallery image deleted successfully."

    def get_related_warning(self, obj):
        return "The image will be permanently removed from the gallery."


@method_decorator(staff_required, name="dispatch")
class MusicManageView(View):
    template_name = "dashboard/music_manage.html"

    def get(self, request):
        search = request.GET.get("q", "").strip()
        category_id = request.GET.get("category", "")
        publication = request.GET.get("publication", "")
        mixes = Mix.objects.select_related("category").order_by("-created_at")
        tracks = Track.objects.select_related("category", "mix").order_by("-created_at")
        if search:
            mixes = mixes.filter(Q(title__icontains=search) | Q(description__icontains=search))
            tracks = tracks.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if category_id.isdigit():
            mixes = mixes.filter(category_id=category_id)
            tracks = tracks.filter(category_id=category_id)
        if publication in {"published", "draft"}:
            is_published = publication == "published"
            mixes = mixes.filter(is_published=is_published)
            tracks = tracks.filter(is_published=is_published)
        mix_page = Paginator(mixes, 15).get_page(request.GET.get("mix_page"))
        track_page = Paginator(tracks, 15).get_page(request.GET.get("track_page"))
        return render(
            request,
            self.template_name,
            {
                "mixes": mix_page.object_list,
                "tracks": track_page.object_list,
                "mix_page": mix_page,
                "track_page": track_page,
                "mix_count": mixes.count(),
                "track_count": tracks.count(),
                "categories": Category.objects.all(),
                "search_query": search,
                "category_filter": category_id,
                "publication_filter": publication,
            },
        )


@method_decorator(staff_required, name="dispatch")
class CategoryManageView(View):
    template_name = "dashboard/categories_manage.html"

    def get(self, request):
        category_groups = []
        definitions = (
            (
                "Music categories",
                Category,
                "portal:music_category_add",
                "portal:music_category_edit",
                "portal:music_category_delete",
                "Track and mix categories remain uncategorized.",
            ),
            (
                "Gallery categories",
                GalleryCategory,
                "portal:gallery_category_add",
                "portal:gallery_category_edit",
                "portal:gallery_category_delete",
                "Gallery images remain uncategorized.",
            ),
            (
                "Video categories",
                VideoCategory,
                "portal:video_category_add",
                "portal:video_category_edit",
                "portal:video_category_delete",
                "Videos remain uncategorized.",
            ),
        )
        for title, model, add_name, edit_name, delete_name, delete_warning in definitions:
            items = [
                {
                    "object": obj,
                    "edit_url": reverse(edit_name, kwargs={"pk": obj.pk}),
                    "delete_url": reverse(delete_name, kwargs={"pk": obj.pk}),
                }
                for obj in model.objects.all()
            ]
            category_groups.append(
                {
                    "title": title,
                    "items": items,
                    "count": len(items),
                    "add_url": reverse(add_name),
                    "delete_warning": delete_warning,
                }
            )
        return render(
            request,
            self.template_name,
            {"category_groups": category_groups},
        )


@method_decorator(superuser_required, name="dispatch")
class GalleryCategoryAddView(CategoryFormView):
    model = GalleryCategory
    form_class = GalleryCategoryForm
    page_title = "Gallery category"


@method_decorator(superuser_required, name="dispatch")
class GalleryCategoryEditView(GalleryCategoryAddView):
    action = "Edit"


@method_decorator(superuser_required, name="dispatch")
class MusicCategoryAddView(CategoryFormView):
    model = Category
    form_class = MusicCategoryForm
    page_title = "Music category"


@method_decorator(superuser_required, name="dispatch")
class MusicCategoryEditView(MusicCategoryAddView):
    action = "Edit"


@method_decorator(superuser_required, name="dispatch")
class VideoCategoryAddView(CategoryFormView):
    model = VideoCategory
    form_class = VideoCategoryForm
    page_title = "Video category"


@method_decorator(superuser_required, name="dispatch")
class VideoCategoryEditView(VideoCategoryAddView):
    action = "Edit"


@method_decorator(superuser_required, name="dispatch")
class GalleryCategoryDeleteView(ContentDeleteView):
    model = GalleryCategory
    list_url_name = "portal:categories"
    success_message = "Gallery category deleted. Images remain and are uncategorized."

    def get_related_warning(self, obj):
        return "Gallery images will be kept and their category will be cleared."


@method_decorator(superuser_required, name="dispatch")
class MusicCategoryDeleteView(ContentDeleteView):
    model = Category
    list_url_name = "portal:categories"
    success_message = "Music category deleted. Tracks and mixes remain uncategorized."

    def get_related_warning(self, obj):
        return "Tracks and mixes will be kept and their category will be cleared."


@method_decorator(superuser_required, name="dispatch")
class VideoCategoryDeleteView(ContentDeleteView):
    model = VideoCategory
    list_url_name = "portal:categories"
    success_message = "Video category deleted. Videos remain uncategorized."

    def get_related_warning(self, obj):
        return "Videos will be kept and their category will be cleared."


@method_decorator(superuser_required, name="dispatch")
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


@method_decorator(superuser_required, name="dispatch")
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


@method_decorator(superuser_required, name="dispatch")
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


@method_decorator(superuser_required, name="dispatch")
class TrackEditView(ContentUploadView):
    page_title = "Edit Music Track"
    back_url = "portal:music"
    submit_label = "Save changes"

    def get(self, request, pk):
        track = get_object_or_404(Track, pk=pk)
        return self.render_form(request, TrackForm(instance=track))

    def post(self, request, pk):
        track = get_object_or_404(Track, pk=pk)
        form = TrackForm(request.POST, request.FILES, instance=track)
        if form.is_valid():
            if not _save_cloudinary_form(form, "music track"):
                return self.render_form(request, form)
            messages.success(request, "Track updated successfully.")
            return redirect("portal:music")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class VideoManageView(View):
    template_name = "dashboard/videos_manage.html"

    def get(self, request):
        queryset = Video.objects.select_related("category").order_by("-created_at")
        search = request.GET.get("q", "").strip()
        publication = request.GET.get("publication", "")
        category_id = request.GET.get("category", "")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        if publication in {"published", "draft"}:
            queryset = queryset.filter(is_published=publication == "published")
        if category_id.isdigit():
            queryset = queryset.filter(category_id=category_id)
        page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {
                "videos": page_obj.object_list,
                "page_obj": page_obj,
                "video_count": queryset.count(),
                "categories": VideoCategory.objects.all(),
                "search_query": search,
                "publication_filter": publication,
                "category_filter": category_id,
            },
        )


@method_decorator(superuser_required, name="dispatch")
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
            return redirect("portal:videos")
        return self.render_form(request, form)


@method_decorator(superuser_required, name="dispatch")
class VideoEditView(ContentUploadView):
    page_title = "Edit Video"
    back_url = "portal:videos"
    submit_label = "Save changes"

    def get(self, request, pk):
        video = get_object_or_404(Video, pk=pk)
        return self.render_form(request, VideoForm(instance=video))

    def post(self, request, pk):
        video = get_object_or_404(Video, pk=pk)
        form = VideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            if not _save_cloudinary_form(form, "video"):
                return self.render_form(request, form)
            messages.success(request, "Video updated successfully.")
            return redirect("portal:videos")
        return self.render_form(request, form)


@method_decorator(staff_required, name="dispatch")
class BiographyManageView(View):
    template_name = "dashboard/biographies_manage.html"

    def get(self, request):
        queryset = Biography.objects.order_by("-updated_at")
        search = request.GET.get("q", "").strip()
        publication = request.GET.get("publication", "")
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(body__icontains=search))
        if publication in {"published", "draft"}:
            queryset = queryset.filter(is_published=publication == "published")
        page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
        return render(
            request,
            self.template_name,
            {
                "biographies": page_obj.object_list,
                "page_obj": page_obj,
                "biography_count": queryset.count(),
                "search_query": search,
                "publication_filter": publication,
            },
        )


class BiographyFormView(View):
    template_name = "dashboard/biography_form.html"
    action = "Add"

    def render_form(self, request, form):
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "action": self.action,
                "cloudinary_configured": not settings.CLOUDINARY_MISSING_SETTINGS,
            },
        )

    def get(self, request, pk=None):
        instance = get_object_or_404(Biography, pk=pk) if pk else None
        return self.render_form(request, BiographyForm(instance=instance))

    def post(self, request, pk=None):
        instance = get_object_or_404(Biography, pk=pk) if pk else None
        form = BiographyForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            if not _save_cloudinary_form(form, "biography"):
                return self.render_form(request, form)
            action = "created" if self.action == "Add" else "updated"
            messages.success(request, f"Biography {action} successfully.")
            return redirect("portal:biographies")
        return self.render_form(request, form)


@method_decorator(superuser_required, name="dispatch")
class BiographyAddView(BiographyFormView):
    action = "Add"


@method_decorator(superuser_required, name="dispatch")
class BiographyEditView(BiographyFormView):
    action = "Edit"


@method_decorator(staff_required, name="dispatch")
class GalleryImageDetailView(ContentDetailView):
    model = GalleryImage
    field_names = ("description", "category", "is_published", "is_featured", "order", "created_at")
    edit_url_name = "portal:gallery_edit"
    delete_url_name = "portal:gallery_delete"
    publish_url_name = "portal:gallery_publish"
    list_url_name = "portal:gallery"


@method_decorator(staff_required, name="dispatch")
class MixDetailManagementView(ContentDetailView):
    model = Mix
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    field_names = ("description", "audio_file", "cover_image", "category", "tracklist", "is_published", "is_featured")
    edit_url_name = "portal:mix_edit"
    delete_url_name = "portal:mix_delete"
    publish_url_name = "portal:mix_publish"
    list_url_name = "portal:music"


@method_decorator(staff_required, name="dispatch")
class TrackDetailManagementView(ContentDetailView):
    model = Track
    field_names = ("description", "audio_file", "cover_image", "mix", "category", "is_published", "is_featured")
    edit_url_name = "portal:track_edit"
    delete_url_name = "portal:track_delete"
    publish_url_name = "portal:track_publish"
    list_url_name = "portal:music"


@method_decorator(staff_required, name="dispatch")
class VideoDetailManagementView(ContentDetailView):
    model = Video
    field_names = ("description", "video_file", "thumbnail", "category", "is_published", "is_featured")
    edit_url_name = "portal:video_edit"
    delete_url_name = "portal:video_delete"
    publish_url_name = "portal:video_publish"
    list_url_name = "portal:videos"


@method_decorator(staff_required, name="dispatch")
class BiographyDetailView(ContentDetailView):
    model = Biography
    field_names = ("body", "profile_image", "is_published", "created_at", "updated_at")
    edit_url_name = "portal:biography_edit"
    delete_url_name = "portal:biography_delete"
    publish_url_name = "portal:biography_publish"
    list_url_name = "portal:biographies"


@method_decorator(superuser_required, name="dispatch")
class GalleryPublishView(ContentPublishView):
    model = GalleryImage
    list_url_name = "portal:gallery"


@method_decorator(superuser_required, name="dispatch")
class MixPublishView(ContentPublishView):
    model = Mix
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    list_url_name = "portal:music"


@method_decorator(superuser_required, name="dispatch")
class TrackPublishView(ContentPublishView):
    model = Track
    list_url_name = "portal:music"


@method_decorator(superuser_required, name="dispatch")
class VideoPublishView(ContentPublishView):
    model = Video
    list_url_name = "portal:videos"


@method_decorator(superuser_required, name="dispatch")
class BiographyPublishView(ContentPublishView):
    model = Biography
    list_url_name = "portal:biographies"


@method_decorator(superuser_required, name="dispatch")
class MixDeleteView(ContentDeleteView):
    model = Mix
    lookup_field = "slug"
    lookup_url_kwarg = "slug"
    list_url_name = "portal:music"
    success_message = "Mix deleted successfully. Associated tracks were retained."

    def get_related_warning(self, obj):
        return "Tracks linked to this mix will remain in your library but will no longer be grouped under it."


@method_decorator(superuser_required, name="dispatch")
class TrackDeleteView(ContentDeleteView):
    model = Track
    list_url_name = "portal:music"
    success_message = "Track deleted successfully."


@method_decorator(superuser_required, name="dispatch")
class VideoDeleteView(ContentDeleteView):
    model = Video
    list_url_name = "portal:videos"
    success_message = "Video deleted successfully."


@method_decorator(superuser_required, name="dispatch")
class BiographyDeleteView(ContentDeleteView):
    model = Biography
    list_url_name = "portal:biographies"
    success_message = "Biography deleted successfully."


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


@method_decorator(superuser_required, name="dispatch")
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
