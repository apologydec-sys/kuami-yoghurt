from django.db.models import F
from django.views.generic import DetailView, ListView

from .forms import VideoSearchForm
from .models import Video, VideoCategory


class VideoListView(ListView):
    model = Video
    template_name = "videos/video_list.html"
    context_object_name = "videos"
    paginate_by = 12

    def get_queryset(self):
        qs = Video.objects.filter(is_published=True).select_related("category")
        form = VideoSearchForm(self.request.GET)
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
        ctx["search_form"] = VideoSearchForm(self.request.GET)
        ctx["categories"] = VideoCategory.objects.all()
        return ctx


class VideoDetailView(DetailView):
    model = Video
    template_name = "videos/video_detail.html"
    context_object_name = "video"

    def get_queryset(self):
        return Video.objects.filter(is_published=True).select_related("category")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        Video.objects.filter(pk=obj.pk).update(play_count=F("play_count") + 1)
        return obj
