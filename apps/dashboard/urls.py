from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("bookings/", views.BookingListView.as_view(), name="bookings"),
    path("bookings/<uuid:reference>/", views.BookingDetailView.as_view(), name="booking_detail"),
    path("bookings/<uuid:reference>/quotation/", views.QuotationCreateUpdateView.as_view(), name="quotation"),
    path("bookings/<uuid:reference>/status/", views.BookingStatusUpdateView.as_view(), name="booking_status"),
    path("bookings/<uuid:reference>/notes/", views.InternalNoteUpdateView.as_view(), name="booking_notes"),
    path("messages/", views.ContactMessageListView.as_view(), name="messages"),
    path("gallery/", views.GalleryManageView.as_view(), name="gallery"),
    path("gallery/upload/", views.GalleryUploadView.as_view(), name="gallery_upload"),
    path("gallery/<int:pk>/delete/", views.GalleryDeleteView.as_view(), name="gallery_delete"),
    path("music/", views.MusicManageView.as_view(), name="music"),
    path("music/mix/add/", views.MixAddView.as_view(), name="mix_add"),
    path("music/mix/<slug:slug>/edit/", views.MixEditView.as_view(), name="mix_edit"),
    path("music/track/add/", views.TrackAddView.as_view(), name="track_add"),
    path("videos/", views.VideoManageView.as_view(), name="videos"),
    path("videos/add/", views.VideoAddView.as_view(), name="video_add"),
    path("chat/", views.ChatAdminListView.as_view(), name="chat"),
    path("chat/<int:pk>/", views.ChatAdminReplyView.as_view(), name="chat_reply"),
    path("site-settings/", views.SiteSettingsView.as_view(), name="site_settings"),
]
