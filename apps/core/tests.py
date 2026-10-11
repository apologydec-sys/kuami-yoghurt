import datetime

from django.test import TestCase
from django.urls import reverse

from .models import Biography, ContactMessage, SiteSettings


class SiteSettingsTest(TestCase):
    def test_get_or_create_singleton(self):
        settings = SiteSettings.get_settings()
        self.assertEqual(settings.pk, 1)
        self.assertEqual(settings.site_name, "DJ Kuami Yoghurt")

    def test_singleton_enforced(self):
        s1 = SiteSettings.get_settings()
        s2 = SiteSettings.get_settings()
        self.assertEqual(s1.pk, s2.pk)


class BiographyTest(TestCase):
    def test_create_biography(self):
        bio = Biography.objects.create(title="My Story", body="Born in Ghana…")
        self.assertEqual(str(bio), "My Story")
        self.assertTrue(bio.is_published)


class ContactMessageTest(TestCase):
    def test_create_contact_message(self):
        msg = ContactMessage.objects.create(
            name="Alice",
            email="alice@example.com",
            subject="Hello",
            message="Test message",
        )
        self.assertFalse(msg.is_read)
        self.assertIn("Alice", str(msg))


# ── View tests added for FEAT-002 ──────────────────────────────────────────


class HomeViewTest(TestCase):
    def test_home_returns_200(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)

    def test_home_hero_uses_existing_public_routes(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'class="public-site"')
        self.assertContains(response, 'class="hero hero--immersive"')
        self.assertContains(response, reverse("music:mix_list"))
        self.assertContains(response, reverse("videos:list"))
        self.assertContains(response, reverse("bookings:create"))


class AboutViewTest(TestCase):
    def test_about_returns_200(self):
        response = self.client.get(reverse("core:about"))
        self.assertEqual(response.status_code, 200)


class ContactViewTest(TestCase):
    def test_contact_get_returns_200(self):
        response = self.client.get(reverse("core:contact"))
        self.assertEqual(response.status_code, 200)

    def test_contact_form_submission_saves_message(self):
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "",
            "subject": "Test Subject",
            "message": "This is a test message body.",
        }
        response = self.client.post(reverse("core:contact"), data)
        # Should redirect to success page
        self.assertRedirects(response, reverse("core:contact_success"))
        self.assertEqual(ContactMessage.objects.count(), 1)
        msg = ContactMessage.objects.first()
        self.assertEqual(msg.name, "Test User")
        self.assertEqual(msg.email, "test@example.com")

    def test_contact_form_rejects_invalid_email(self):
        data = {
            "name": "Bad Email User",
            "email": "not-an-email",
            "subject": "Bad email test",
            "message": "This is a test message body.",
        }
        response = self.client.post(reverse("core:contact"), data)
        # Should re-render the form with errors, not redirect
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_contact_form_rejects_short_message(self):
        data = {
            "name": "Short Msg",
            "email": "short@example.com",
            "subject": "Short message test",
            "message": "Hi",
        }
        response = self.client.post(reverse("core:contact"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
        self.assertEqual(ContactMessage.objects.count(), 0)
