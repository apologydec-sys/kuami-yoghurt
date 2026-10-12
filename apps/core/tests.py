import datetime
import json

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from PIL import Image

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


class PwaExperienceTests(TestCase):
    def test_manifest_has_root_scope_and_install_icons(self):
        response = self.client.get(reverse("pwa_manifest"))
        manifest = json.loads(response.content)

        self.assertEqual(response["Content-Type"].split(";")[0], "application/manifest+json")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(
            {icon["sizes"] for icon in manifest["icons"]},
            {"192x192", "512x512"},
        )
        for icon in manifest["icons"]:
            icon_path = settings.BASE_DIR / "static" / icon["src"].removeprefix("/static/")
            with Image.open(icon_path) as image:
                self.assertEqual(image.size, tuple(map(int, icon["sizes"].split("x"))))

    def test_service_worker_is_root_scoped_and_supplied_without_long_cache(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertContains(response, "isPrivatePath")
        self.assertContains(response, "OFFLINE_URL")
        self.assertContains(response, "request.method !== 'GET'")
        self.assertEqual(
            self.client.post(reverse("service_worker")).status_code,
            405,
        )
        offline_page = (settings.BASE_DIR / "static" / "offline.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("You're offline", offline_page)

    def test_public_shell_offers_install_and_ios_instructions(self):
        response = self.client.get(reverse("core:home"))
        install_script = (
            settings.BASE_DIR / "static" / "js" / "pwa.js"
        ).read_text(encoding="utf-8")

        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'id="pwaInstallButton"')
        self.assertContains(response, "js/pwa.js")
        self.assertIn("Add to Home Screen", install_script)
        self.assertIn("service-worker.js", install_script)

    def test_music_detail_does_not_register_player_twice(self):
        from apps.music.models import Mix

        mix = Mix.objects.create(
            title="Playback initialization test",
            slug="playback-init-test",
            is_published=True,
        )
        response = self.client.get(reverse("music:mix_detail", kwargs={"slug": mix.slug}))
        main_script = (settings.BASE_DIR / "static" / "js" / "main.js").read_text(
            encoding="utf-8"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "window.initAudioPlayer")
        self.assertIn("playerInitialized", main_script)


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
