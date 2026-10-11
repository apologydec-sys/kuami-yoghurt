import datetime

from django.test import TestCase
from django.urls import reverse

from .models import Booking, BookingMessage, BookingStatusHistory, Quotation


class BookingTest(TestCase):
    def _make_booking(self, **kwargs):
        defaults = dict(
            customer_name="John Doe",
            customer_email="john@example.com",
            customer_phone="+233201234567",
            event_type="wedding",
            event_date=datetime.date(2026, 6, 15),
            event_location="Accra, Ghana",
        )
        defaults.update(kwargs)
        return Booking.objects.create(**defaults)

    def test_booking_created_with_received_status(self):
        booking = self._make_booking()
        self.assertEqual(booking.status, "received")

    def test_token_generated(self):
        booking = self._make_booking()
        self.assertTrue(len(booking.token) > 30)

    def test_reference_is_uuid(self):
        booking = self._make_booking()
        self.assertIsNotNone(booking.reference)

    def test_str(self):
        booking = self._make_booking()
        self.assertIn("John Doe", str(booking))


class QuotationTest(TestCase):
    def test_create_quotation(self):
        booking = Booking.objects.create(
            customer_name="Jane Smith",
            customer_email="jane@example.com",
            customer_phone="+233209876543",
            event_type="birthday",
            event_date=datetime.date(2026, 8, 20),
            event_location="Kumasi",
        )
        quotation = Quotation.objects.create(
            booking=booking, amount="1500.00", currency="GHS"
        )
        self.assertEqual(quotation.currency, "GHS")
        self.assertIn("Jane Smith", str(quotation))


class BookingStatusHistoryTest(TestCase):
    def test_create_history_entry(self):
        booking = Booking.objects.create(
            customer_name="Sam",
            customer_email="sam@example.com",
            customer_phone="+233201111111",
            event_type="club",
            event_date=datetime.date(2026, 12, 31),
            event_location="Osu, Accra",
        )
        history = BookingStatusHistory.objects.create(
            booking=booking, status="under_review"
        )
        self.assertEqual(history.status, "under_review")


# ── View tests added for FEAT-002 ──────────────────────────────────────────

_FUTURE_DATE = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
_PAST_DATE = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

_VALID_FORM_DATA = {
    "customer_name": "Test Customer",
    "customer_email": "customer@example.com",
    "customer_phone": "+233201234567",
    "event_type": "wedding",
    "event_date": _FUTURE_DATE,
    "event_time": "",
    "event_location": "Accra International Conference Centre",
    "guest_count": "100",
    "music_preferences": "Highlife and Afrobeats",
    "additional_requirements": "",
}


class BookingCreateViewTest(TestCase):
    def test_booking_form_get_returns_200(self):
        response = self.client.get(reverse("bookings:create"))
        self.assertEqual(response.status_code, 200)

    def test_valid_booking_creates_record_and_redirects(self):
        response = self.client.post(reverse("bookings:create"), _VALID_FORM_DATA)
        self.assertEqual(Booking.objects.count(), 1)
        booking = Booking.objects.first()
        self.assertEqual(booking.status, "received")
        self.assertTrue(len(booking.token) > 30)
        # Should redirect to the success page with the token in the URL
        self.assertRedirects(
            response,
            reverse("bookings:success", kwargs={"token": booking.token}),
        )

    def test_valid_booking_creates_status_history(self):
        self.client.post(reverse("bookings:create"), _VALID_FORM_DATA)
        booking = Booking.objects.first()
        self.assertEqual(booking.status_history.count(), 1)
        entry = booking.status_history.first()
        self.assertEqual(entry.status, "received")

    def test_past_date_rejected(self):
        data = dict(_VALID_FORM_DATA, event_date=_PAST_DATE)
        response = self.client.post(reverse("bookings:create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertEqual(Booking.objects.count(), 0)

    def test_rate_limit_blocks_second_submission(self):
        self.client.post(reverse("bookings:create"), _VALID_FORM_DATA)
        # Second immediate submission should be rate-limited
        response = self.client.post(reverse("bookings:create"), _VALID_FORM_DATA)
        # Rate-limited: form_invalid path returns 200, and no second booking created
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)


class BookingTrackingViewTest(TestCase):
    def _make_booking(self):
        return Booking.objects.create(
            customer_name="Tracking User",
            customer_email="tracking@example.com",
            customer_phone="+233200000001",
            event_type="birthday",
            event_date=datetime.date(2026, 9, 10),
            event_location="Cape Coast",
        )

    def test_tracking_returns_200_with_valid_token(self):
        booking = self._make_booking()
        response = self.client.get(
            reverse("bookings:track", kwargs={"token": booking.token})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["booking"], booking)

    def test_tracking_returns_404_with_wrong_token(self):
        response = self.client.get(
            reverse("bookings:track", kwargs={"token": "totally-invalid-token-xyz"})
        )
        self.assertEqual(response.status_code, 404)


class QuotationResponseViewTest(TestCase):
    def _make_booking_with_quotation(self):
        booking = Booking.objects.create(
            customer_name="Quotation Tester",
            customer_email="qt@example.com",
            customer_phone="+233200000002",
            event_type="corporate",
            event_date=datetime.date(2026, 11, 1),
            event_location="Labadi Beach",
            status="quotation_sent",
        )
        Quotation.objects.create(booking=booking, amount="2000.00", currency="GHS")
        return booking

    def test_accept_quotation_changes_status_to_confirmed(self):
        booking = self._make_booking_with_quotation()
        self.client.post(
            reverse("bookings:respond", kwargs={"token": booking.token}),
            {"action": "accept"},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, "confirmed")

    def test_decline_quotation_changes_status_to_declined(self):
        booking = self._make_booking_with_quotation()
        self.client.post(
            reverse("bookings:respond", kwargs={"token": booking.token}),
            {"action": "decline"},
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, "declined")

    def test_replay_prevented_after_acceptance(self):
        """Customer cannot re-respond once the status has moved past quotation_sent."""
        booking = self._make_booking_with_quotation()
        url = reverse("bookings:respond", kwargs={"token": booking.token})
        # First: accept
        self.client.post(url, {"action": "accept"})
        booking.refresh_from_db()
        self.assertEqual(booking.status, "confirmed")
        # Second attempt: should be rejected (status != quotation_sent)
        response = self.client.post(url, {"action": "accept"})
        self.assertEqual(response.status_code, 400)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "confirmed")  # unchanged
