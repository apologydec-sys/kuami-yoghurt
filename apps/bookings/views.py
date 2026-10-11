import datetime

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import BookingForm
from .models import Booking, BookingStatusHistory
from .utils import generate_booking_token, get_client_ip

# Session key used for basic rate limiting on booking submissions.
_LAST_BOOKING_SESSION_KEY = "last_booking_submitted_at"
_BOOKING_RATE_LIMIT_SECONDS = 60


class BookingCreateView(FormView):
    template_name = "bookings/booking_form.html"
    form_class = BookingForm

    def _is_rate_limited(self, request):
        last_ts = request.session.get(_LAST_BOOKING_SESSION_KEY)
        if last_ts is None:
            return False
        elapsed = datetime.datetime.now().timestamp() - last_ts
        return elapsed < _BOOKING_RATE_LIMIT_SECONDS

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rate_limited"] = self._is_rate_limited(self.request)
        return ctx

    def form_valid(self, form):
        if self._is_rate_limited(self.request):
            form.add_error(None, "Please wait a moment before submitting another booking request.")
            return self.form_invalid(form)

        cd = form.cleaned_data
        token = generate_booking_token()

        booking = Booking.objects.create(
            token=token,
            customer_name=cd["customer_name"],
            customer_email=cd["customer_email"],
            customer_phone=cd["customer_phone"],
            event_type=cd["event_type"],
            event_date=cd["event_date"],
            event_time=cd.get("event_time"),
            event_location=cd["event_location"],
            guest_count=cd.get("guest_count"),
            music_preferences=cd.get("music_preferences", ""),
            additional_requirements=cd.get("additional_requirements", ""),
            status="received",
            ip_address=get_client_ip(self.request),
        )

        BookingStatusHistory.objects.create(
            booking=booking,
            status="received",
            note="Booking request submitted by customer.",
        )

        # Record rate-limit timestamp in session.
        self.request.session[_LAST_BOOKING_SESSION_KEY] = (
            datetime.datetime.now().timestamp()
        )

        return redirect("bookings:success", token=booking.token)


class BookingSuccessView(TemplateView):
    template_name = "bookings/booking_success.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        token = self.kwargs.get("token", "")
        # Provide the booking object so the template can show the reference.
        # Use filter + first to avoid timing attacks; returns None if not found.
        ctx["booking"] = Booking.objects.filter(token=token).first()
        ctx["token"] = token
        return ctx


class BookingTrackingView(View):
    template_name = "bookings/booking_tracking.html"

    def get(self, request, token):
        # Never distinguish "wrong token" from "no booking found" to prevent enumeration.
        booking = Booking.objects.filter(token=token).select_related("quotation").first()
        if booking is None:
            raise Http404
        history = booking.status_history.all()
        messages = booking.messages.all()
        return render(
            request,
            self.template_name,
            {
                "booking": booking,
                "history": history,
                "messages": messages,
            },
        )


class QuotationResponseView(View):
    """Accepts a customer's accept/decline decision on a quotation."""

    def post(self, request, token):
        booking = Booking.objects.filter(token=token).first()
        if booking is None:
            raise Http404

        # Guard: only allow response when status is quotation_sent.
        if booking.status != "quotation_sent":
            return render(
                request,
                "bookings/quotation_response_error.html",
                {
                    "booking": booking,
                    "error": "This quotation cannot be responded to in its current state.",
                },
                status=400,
            )

        action = request.POST.get("action", "").strip()
        if action not in ("accept", "decline"):
            return render(
                request,
                "bookings/quotation_response_error.html",
                {"booking": booking, "error": "Invalid response."},
                status=400,
            )

        new_status = "confirmed" if action == "accept" else "declined"
        note = "Customer accepted the quotation." if action == "accept" else "Customer declined the quotation."

        booking.status = new_status
        booking.save(update_fields=["status", "updated_at"])

        BookingStatusHistory.objects.create(
            booking=booking,
            status=new_status,
            note=note,
        )

        return redirect("bookings:track", token=booking.token)
