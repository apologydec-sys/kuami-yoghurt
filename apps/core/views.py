from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView, FormView

from apps.gallery.models import GalleryImage
from apps.music.models import Mix, Track
from apps.videos.models import Video
from .forms import ContactForm
from .models import Biography, ContactMessage, SiteSettings


@require_GET
def pwa_manifest(request):
    manifest = (settings.BASE_DIR / "static" / "site.webmanifest").read_text(
        encoding="utf-8"
    )
    response = HttpResponse(manifest, content_type="application/manifest+json")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def service_worker(request):
    worker_path = settings.BASE_DIR / "static" / "service-worker.js"
    response = HttpResponse(
        worker_path.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["featured_mixes"] = Mix.objects.filter(
            is_published=True, is_featured=True
        ).select_related("category")[:4]
        ctx["featured_tracks"] = Track.objects.filter(
            is_published=True, is_featured=True
        ).select_related("category")[:4]
        ctx["featured_videos"] = Video.objects.filter(
            is_published=True, is_featured=True
        ).select_related("category")[:3]
        ctx["featured_gallery"] = GalleryImage.objects.filter(
            is_published=True, is_featured=True
        ).select_related("category")[:6]
        return ctx


class AboutView(TemplateView):
    template_name = "core/about.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["biography"] = Biography.objects.filter(is_published=True).first()
        return ctx


class ContactView(FormView):
    template_name = "core/contact.html"
    form_class = ContactForm

    def form_valid(self, form):
        cd = form.cleaned_data
        ContactMessage.objects.create(
            name=cd["name"],
            email=cd["email"],
            phone=cd.get("phone", ""),
            subject=cd["subject"],
            message=cd["message"],
            ip_address=_get_client_ip(self.request),
        )
        return redirect("core:contact_success")

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class ContactSuccessView(TemplateView):
    template_name = "core/contact_success.html"


def handler404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
