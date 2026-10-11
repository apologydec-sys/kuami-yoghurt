from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import MusicSearchForm
from .models import Category, Mix, Track


class MixListView(ListView):
    model = Mix
    template_name = "music/mix_list.html"
    context_object_name = "mixes"
    paginate_by = 12

    def get_queryset(self):
        qs = Mix.objects.filter(is_published=True).select_related("category")
        form = MusicSearchForm(self.request.GET)
        if form.is_valid():
            q = form.cleaned_data.get("q")
            category = form.cleaned_data.get("category")
            if q:
                qs = qs.filter(title__icontains=q)
            if category:
                qs = qs.filter(category=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = MusicSearchForm(self.request.GET)
        return ctx


class MixDetailView(DetailView):
    model = Mix
    template_name = "music/mix_detail.html"
    context_object_name = "mix"

    def get_queryset(self):
        return Mix.objects.filter(is_published=True).select_related("category")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        Mix.objects.filter(pk=obj.pk).update(play_count=F("play_count") + 1)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mix = ctx["mix"]
        ctx["related_mixes"] = (
            Mix.objects.filter(is_published=True, category=mix.category)
            .exclude(pk=mix.pk)
            .select_related("category")[:4]
        )
        return ctx


class TrackListView(ListView):
    model = Track
    template_name = "music/track_list.html"
    context_object_name = "tracks"
    paginate_by = 12

    def get_queryset(self):
        qs = Track.objects.filter(is_published=True).select_related("category", "mix")
        form = MusicSearchForm(self.request.GET)
        if form.is_valid():
            q = form.cleaned_data.get("q")
            category = form.cleaned_data.get("category")
            if q:
                qs = qs.filter(title__icontains=q)
            if category:
                qs = qs.filter(category=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = MusicSearchForm(self.request.GET)
        return ctx


class TrackDetailView(DetailView):
    model = Track
    template_name = "music/track_detail.html"
    context_object_name = "track"

    def get_queryset(self):
        return Track.objects.filter(is_published=True).select_related("category", "mix")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        Track.objects.filter(pk=obj.pk).update(play_count=F("play_count") + 1)
        return obj


class CategoryListView(ListView):
    model = Category
    template_name = "music/category_list.html"
    context_object_name = "categories"


class IncrementPlayCountView(View):
    """AJAX endpoint — increments play_count for a Mix and returns JSON."""

    def post(self, request, slug):
        updated = Mix.objects.filter(slug=slug, is_published=True).update(
            play_count=F("play_count") + 1
        )
        if not updated:
            return JsonResponse({"error": "not found"}, status=404)
        return JsonResponse({"status": "ok"})
