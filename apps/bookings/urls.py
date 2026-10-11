from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("book/", views.BookingCreateView.as_view(), name="create"),
    path("book/success/<str:token>/", views.BookingSuccessView.as_view(), name="success"),
    path("booking/<str:token>/", views.BookingTrackingView.as_view(), name="track"),
    path("booking/<str:token>/respond/", views.QuotationResponseView.as_view(), name="respond"),
]
