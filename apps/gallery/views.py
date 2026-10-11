from django.views.generic import DetailView, ListView

from .models import GalleryCategory, GalleryImage


class GalleryView(ListView):
    model = GalleryImage
    template_name = "gallery/gallery_index.html"
    context_object_name = "images"
    paginate_by = 24

    def get_queryset(self):
        qs = GalleryImage.objects.filter(is_published=True).select_related("category")
        category_slug = self.request.GET.get("category")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = GalleryCategory.objects.all()
        ctx["active_category"] = self.request.GET.get("category", "")
        return ctx


class GalleryDetailView(DetailView):
    model = GalleryImage
    template_name = "gallery/gallery_detail.html"
    context_object_name = "image"

    def get_queryset(self):
        return GalleryImage.objects.filter(is_published=True).select_related("category")
