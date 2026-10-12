from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.bookings.models import Booking, BookingStatusHistory
from apps.chat.models import Conversation, Message

User = get_user_model()


class DashboardAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username="admin_test",
            password="securepass123",
            email="admin@example.com",
        )

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/portal/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/login/", response["Location"])

    def test_authenticated_superuser_can_access(self):
        self.client.force_login(self.superuser)
        response = self.client.get("/portal/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="portal-shell"')
        self.assertNotContains(response, "hero-scene")

    def test_bookings_list_requires_login(self):
        response = self.client.get("/portal/bookings/")
        self.assertEqual(response.status_code, 302)

    def test_authenticated_can_view_bookings(self):
        self.client.force_login(self.superuser)
        response = self.client.get("/portal/bookings/")
        self.assertEqual(response.status_code, 200)

    def test_chat_list_renders_existing_conversation(self):
        self.client.force_login(self.superuser)
        conversation = Conversation.objects.create(
            session_key="portal-chat-list-test",
            customer_name="Existing customer",
        )
        Message.objects.create(
            conversation=conversation,
            content="Existing message",
            is_from_dj=False,
        )
        response = self.client.get("/portal/chat/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Existing customer")
        self.assertEqual(response.context["conversations"][0].unread_message_count, 1)

    def test_portal_login_page_renders(self):
        response = self.client.get("/portal/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Super Admin")
        self.assertContains(response, 'class="portal-shell"')

    def test_anonymous_portal_login_and_missing_trailing_slash(self):
        response = self.client.get("/portal/login/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Super Admin")
        self.assertEqual(response.redirect_chain, [])

        response = self.client.get("/portal/login", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [("/portal/login/", 301)])
        self.assertContains(response, "Super Admin")

    def test_authenticated_superuser_portal_login_redirects_to_dashboard(self):
        self.client.force_login(self.superuser)
        response = self.client.get("/portal/login/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [("/portal/", 302)])
        self.assertEqual(response.request["PATH_INFO"], "/portal/")
        self.assertContains(response, 'class="portal-shell"')

        response = self.client.get("/portal/login", follow=True)
        self.assertEqual(
            response.redirect_chain,
            [("/portal/login/", 301), ("/portal/", 302)],
        )
        self.assertEqual(response.status_code, 200)

    def test_authenticated_non_admin_does_not_loop_on_portal_login(self):
        customer = User.objects.create_user(
            username="portal-customer",
            password="NotTheAdminPassword!123",
            is_staff=False,
            is_superuser=False,
        )
        self.client.force_login(customer)
        response = self.client.get("/portal/login/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [])
        self.assertContains(response, "Super Admin")

        response = self.client.get("/portal/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [("/portal/login/?next=/portal/", 302)],
        )
        self.assertContains(response, "Super Admin")

    def test_non_staff_user_cannot_access_portal(self):
        user = User.objects.create_user(username="customer", password="pass123", is_staff=False)
        self.client.force_login(user)
        response = self.client.get("/portal/")
        self.assertEqual(response.status_code, 302)


class BookingStatusUpdateTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username="admin_status_test",
            password="securepass456",
            email="admin2@example.com",
        )
        self.booking = Booking.objects.create(
            customer_name="Kofi Mensah",
            customer_email="kofi@example.com",
            customer_phone="0201234567",
            event_type="wedding",
            event_date="2030-01-15",
            event_location="Accra, Ghana",
            status="received",
        )

    def test_status_update_creates_history_entry(self):
        self.client.force_login(self.superuser)
        initial_count = BookingStatusHistory.objects.filter(
            booking=self.booking
        ).count()

        response = self.client.post(
            "/dashboard/bookings/{}/status/".format(self.booking.reference),
            {"status": "under_review", "note": "Being reviewed now."},
        )
        self.assertEqual(response.status_code, 302)

        # A new history entry must have been created.
        new_count = BookingStatusHistory.objects.filter(booking=self.booking).count()
        self.assertEqual(new_count, initial_count + 1)

        # The booking status must be updated.
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "under_review")

        # The history entry must reference the correct status and user.
        entry = BookingStatusHistory.objects.filter(
            booking=self.booking, status="under_review"
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.changed_by, self.superuser)
        self.assertEqual(entry.note, "Being reviewed now.")
