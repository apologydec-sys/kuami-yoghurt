from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.GalleryView.as_view(), name="index"),
    path("<int:pk>/", views.GalleryDetailView.as_view(), name="detail"),
]
