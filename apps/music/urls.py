from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
    path("mixes/", views.MixListView.as_view(), name="mix_list"),
    path("mixes/<slug:slug>/", views.MixDetailView.as_view(), name="mix_detail"),
    path("mixes/<slug:slug>/play/", views.IncrementPlayCountView.as_view(), name="increment_play"),
    path("tracks/", views.TrackListView.as_view(), name="track_list"),
    path("tracks/<slug:slug>/", views.TrackDetailView.as_view(), name="track_detail"),
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
]
