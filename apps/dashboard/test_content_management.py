from unittest.mock import patch

from cloudinary.exceptions import Error as CloudinaryError
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.core.models import Biography, SiteSettings
from apps.gallery.models import GalleryCategory, GalleryImage
from apps.music.models import Category, Mix, Track
from apps.videos.models import Video, VideoCategory


class SuperadminContentManagementTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superadmin = user_model.objects.create_superuser(
            username="content_superadmin",
            email="content-admin@example.com",
            password="not-a-real-production-password",
        )
        self.staff = user_model.objects.create_user(
            username="content_staff",
            email="content-staff@example.com",
            password="not-a-real-production-password",
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.superadmin)

    def confirm_delete(self, path, expected_redirect):
        confirmation = self.client.get(path)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Confirm delete")
        response = self.client.post(path, {"confirm_delete": "1"})
        self.assertRedirects(response, expected_redirect)
        return response

    def test_category_crud_preserves_related_content(self):
        music_response = self.client.post(
            "/portal/music/categories/add/",
            {"name": "Afrobeats", "description": "Dance music", "order": "2"},
        )
        self.assertRedirects(music_response, "/portal/gallery/categories/")
        music_category = Category.objects.get(name="Afrobeats")
        self.assertEqual(music_category.slug, "afrobeats")
        duplicate_category = self.client.post(
            "/portal/music/categories/add/",
            {"name": "Afrobeats", "description": "Duplicate", "order": "0"},
        )
        self.assertEqual(duplicate_category.status_code, 200)
        self.assertContains(duplicate_category, "already exists")
        self.assertEqual(Category.objects.filter(slug="afrobeats").count(), 1)
        music_edit = self.client.post(
            f"/portal/music/categories/{music_category.pk}/edit/",
            {"name": "Afrobeats & Highlife", "description": "Updated", "order": "1"},
        )
        self.assertRedirects(music_edit, "/portal/gallery/categories/")
        music_category.refresh_from_db()
        self.assertEqual(music_category.name, "Afrobeats & Highlife")

        track = Track.objects.create(
            title="Test track", audio_file="test/audio/track", category=music_category
        )
        self.confirm_delete(
            f"/portal/music/categories/{music_category.pk}/delete/",
            "/portal/gallery/categories/",
        )
        track.refresh_from_db()
        self.assertIsNone(track.category_id)

        gallery_category_response = self.client.post(
            "/portal/gallery/categories/add/",
            {"name": "Events", "order": "2"},
        )
        self.assertRedirects(gallery_category_response, "/portal/gallery/categories/")
        gallery_category = GalleryCategory.objects.get(name="Events")
        video_category_response = self.client.post(
            "/portal/videos/categories/add/",
            {"name": "Live sets", "order": "1"},
        )
        self.assertRedirects(video_category_response, "/portal/gallery/categories/")
        video_category = VideoCategory.objects.get(name="Live sets")
        gallery_image = GalleryImage.objects.create(
            title="Stage", image="test/gallery/stage", category=gallery_category
        )
        video = Video.objects.create(
            title="Stage video",
            slug="stage-video",
            video_file="test/video/stage",
            category=video_category,
        )
        self.client.post(
            f"/portal/gallery/categories/{gallery_category.pk}/edit/",
            {"name": "Event photos", "order": "0"},
        )
        gallery_category.refresh_from_db()
        self.assertEqual(gallery_category.name, "Event photos")
        self.client.post(
            f"/portal/videos/categories/{video_category.pk}/edit/",
            {"name": "Live performances", "order": "0"},
        )
        video_category.refresh_from_db()
        self.assertEqual(video_category.name, "Live performances")
        self.confirm_delete(
            f"/portal/gallery/categories/{gallery_category.pk}/delete/",
            "/portal/gallery/categories/",
        )
        self.confirm_delete(
            f"/portal/videos/categories/{video_category.pk}/delete/",
            "/portal/gallery/categories/",
        )
        gallery_image.refresh_from_db()
        video.refresh_from_db()
        self.assertIsNone(gallery_image.category_id)
        self.assertIsNone(video.category_id)

    def test_manage_lists_show_content_details_and_filter_counts(self):
        category = Category.objects.create(name="Dance")
        Mix.objects.create(
            title="Night mix", slug="night-mix", category=category, is_published=True
        )
        Track.objects.create(
            title="Night track", slug="night-track", category=category, is_published=False
        )
        GalleryImage.objects.create(
            title="Night image", image="test/gallery/night", is_published=False
        )
        Video.objects.create(
            title="Night video", slug="night-video", is_published=True
        )
        Biography.objects.create(title="About the DJ", body="A biography.")

        for path, expected_title in (
            ("/portal/music/?q=Night", "Night mix"),
            ("/portal/gallery/?publication=draft", "Night image"),
            ("/portal/videos/?publication=published", "Night video"),
            ("/portal/biographies/?q=About", "About the DJ"),
            ("/portal/gallery/categories/", "Music categories"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_title)

    def test_portal_and_upload_layouts_include_responsive_breakpoints(self):
        response = self.client.get("/portal/gallery/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "min-width: 769px")
        self.assertContains(response, "max-width: 768px")
        self.assertContains(response, "overflow-x: auto")

        upload_response = self.client.get("/portal/gallery/upload/")
        self.assertEqual(upload_response.status_code, 200)
        self.assertContains(upload_response, "max-width: 480px")
        self.assertContains(upload_response, "upload-form__actions")

    def test_create_read_edit_publish_and_unpublish_biography(self):
        create_response = self.client.post(
            "/portal/biographies/add/",
            {"title": "Biography", "body": "First version", "is_published": ""},
        )
        self.assertRedirects(create_response, "/portal/biographies/")
        biography = Biography.objects.get(title="Biography")
        self.assertFalse(biography.is_published)

        detail = self.client.get(f"/portal/biographies/{biography.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "First version")

        edit_response = self.client.post(
            f"/portal/biographies/{biography.pk}/edit/",
            {"title": "Biography updated", "body": "Second version"},
        )
        self.assertRedirects(edit_response, "/portal/biographies/")
        biography.refresh_from_db()
        self.assertEqual(biography.body, "Second version")
        self.assertFalse(biography.is_published)

        self.client.post(f"/portal/biographies/{biography.pk}/publish/")
        biography.refresh_from_db()
        self.assertTrue(biography.is_published)
        self.client.post(f"/portal/biographies/{biography.pk}/publish/")
        biography.refresh_from_db()
        self.assertFalse(biography.is_published)

        self.confirm_delete(
            f"/portal/biographies/{biography.pk}/delete/",
            "/portal/biographies/",
        )
        self.assertFalse(Biography.objects.filter(pk=biography.pk).exists())

    def test_update_preserves_publication_when_advanced_settings_are_closed(self):
        category = GalleryCategory.objects.create(name="Featured")
        gallery = GalleryImage.objects.create(
            title="Published photo",
            image="test/gallery/published",
            category=category,
            is_featured=True,
            is_published=True,
            order=7,
        )
        self.client.post(
            f"/portal/gallery/{gallery.pk}/edit/",
            {"title": "Renamed photo", "description": "Changed caption"},
        )
        gallery.refresh_from_db()
        self.assertEqual(gallery.title, "Renamed photo")
        self.assertTrue(gallery.is_published)
        self.assertTrue(gallery.is_featured)
        self.assertEqual(gallery.order, 7)
        self.assertEqual(gallery.category_id, category.pk)

    @patch("apps.dashboard.views.uploader.destroy")
    def test_gallery_music_and_video_crud_and_publication_lifecycle(self, destroy):
        gallery = GalleryImage.objects.create(
            title="Portrait", image="test/gallery/portrait", is_published=False
        )
        mix = Mix.objects.create(
            title="Weekend mix",
            slug="weekend-mix",
            audio_file="test/music/weekend-mix",
            cover_image="test/music/weekend-cover",
        )
        track = Track.objects.create(
            title="Weekend track",
            slug="weekend-track",
            audio_file="test/music/weekend-track",
        )
        video = Video.objects.create(
            title="Weekend video",
            slug="weekend-video",
            video_file="test/video/weekend",
            thumbnail="test/video/weekend-cover",
        )

        edit_cases = (
            (
                f"/portal/gallery/{gallery.pk}/edit/",
                {"title": "Portrait updated", "description": "Edited caption"},
                gallery,
            ),
            (
                "/portal/music/mix/weekend-mix/edit/",
                {"title": "Weekend mix updated", "description": "Edited mix"},
                mix,
            ),
            (
                f"/portal/music/track/{track.pk}/edit/",
                {"title": "Weekend track updated", "description": "Edited track"},
                track,
            ),
            (
                f"/portal/videos/{video.pk}/edit/",
                {"title": "Weekend video updated", "description": "Edited video"},
                video,
            ),
        )
        for path, data, instance in edit_cases:
            with self.subTest(path=path):
                response = self.client.post(path, data)
                self.assertEqual(response.status_code, 302)
                instance.refresh_from_db()
                self.assertIn("updated", instance.title)

        for path, instance in (
            (f"/portal/gallery/{gallery.pk}/publish/", gallery),
            ("/portal/music/mix/weekend-mix/publish/", mix),
            (f"/portal/music/track/{track.pk}/publish/", track),
            (f"/portal/videos/{video.pk}/publish/", video),
        ):
            with self.subTest(path=path):
                self.client.post(path)
                instance.refresh_from_db()
                self.assertTrue(instance.is_published)
                self.client.post(path)
                instance.refresh_from_db()
                self.assertFalse(instance.is_published)

        delete_cases = (
            (f"/portal/gallery/{gallery.pk}/delete/", "/portal/gallery/"),
            ("/portal/music/mix/weekend-mix/delete/", "/portal/music/"),
            (f"/portal/music/track/{track.pk}/delete/", "/portal/music/"),
            (f"/portal/videos/{video.pk}/delete/", "/portal/videos/"),
        )
        for path, destination in delete_cases:
            with self.subTest(path=path):
                self.confirm_delete(path, destination)
        self.assertFalse(GalleryImage.objects.filter(pk=gallery.pk).exists())
        self.assertFalse(Mix.objects.filter(pk=mix.pk).exists())
        self.assertFalse(Track.objects.filter(pk=track.pk).exists())
        self.assertFalse(Video.objects.filter(pk=video.pk).exists())
        self.assertEqual(destroy.call_count, 6)

    def test_all_content_detail_pages_render_and_delete_confirmations_identify_item(self):
        category = Category.objects.create(name="Test category")
        image = GalleryImage.objects.create(title="Gallery item", image="test/image")
        mix = Mix.objects.create(title="Mix item", slug="mix-item")
        track = Track.objects.create(title="Track item", slug="track-item")
        video = Video.objects.create(title="Video item", slug="video-item")
        biography = Biography.objects.create(title="Biography item", body="Details")

        cases = (
            (f"/portal/gallery/{image.pk}/", f"/portal/gallery/{image.pk}/delete/", "Gallery item"),
            ("/portal/music/mix/mix-item/", "/portal/music/mix/mix-item/delete/", "Mix item"),
            (f"/portal/music/track/{track.pk}/", f"/portal/music/track/{track.pk}/delete/", "Track item"),
            (f"/portal/videos/{video.pk}/", f"/portal/videos/{video.pk}/delete/", "Video item"),
            (f"/portal/biographies/{biography.pk}/", f"/portal/biographies/{biography.pk}/delete/", "Biography item"),
        )
        for detail_path, delete_path, title in cases:
            with self.subTest(detail_path=detail_path):
                detail_response = self.client.get(detail_path)
                self.assertEqual(detail_response.status_code, 200)
                self.assertContains(detail_response, title)
                confirmation = self.client.get(delete_path)
                self.assertEqual(confirmation.status_code, 200)
                self.assertContains(confirmation, title)

        self.assertTrue(Category.objects.filter(pk=category.pk).exists())
        self.assertTrue(Mix.objects.filter(pk=mix.pk).exists())

    @patch("apps.dashboard.views.uploader.destroy")
    def test_media_delete_only_removes_unshared_cloudinary_assets(self, destroy):
        first = GalleryImage.objects.create(
            title="Shared image one", image="shared/gallery/item"
        )
        second = GalleryImage.objects.create(
            title="Shared image two", image="shared/gallery/item"
        )

        self.confirm_delete(
            f"/portal/gallery/{first.pk}/delete/",
            "/portal/gallery/",
        )
        destroy.assert_not_called()
        self.assertTrue(GalleryImage.objects.filter(pk=second.pk).exists())

        self.confirm_delete(
            f"/portal/gallery/{second.pk}/delete/",
            "/portal/gallery/",
        )
        destroy.assert_called_once_with("shared/gallery/item", resource_type="image")

    @patch(
        "apps.dashboard.views.uploader.destroy",
        side_effect=CloudinaryError("simulated delete failure"),
    )
    def test_media_cleanup_failure_reports_warning_after_record_delete(self, destroy):
        image = GalleryImage.objects.create(
            title="Cleanup failure", image="test/gallery/cleanup-failure"
        )

        response = self.client.post(
            f"/portal/gallery/{image.pk}/delete/",
            {"confirm_delete": "1"},
            follow=True,
        )

        self.assertFalse(GalleryImage.objects.filter(pk=image.pk).exists())
        self.assertContains(response, "media files could not be removed")
        destroy.assert_called_once()

    def test_singleton_site_settings_can_be_viewed_and_updated_but_not_deleted(self):
        response = self.client.get("/portal/site-settings/")
        self.assertEqual(response.status_code, 200)
        update = self.client.post(
            "/portal/site-settings/",
            {"site_name": "Updated DJ site"},
        )
        self.assertRedirects(update, "/dashboard/site-settings/")
        self.assertEqual(SiteSettings.objects.get(pk=1).site_name, "Updated DJ site")

    def test_non_superusers_cannot_create_edit_publish_or_delete_content(self):
        gallery = GalleryImage.objects.create(
            title="Protected gallery image", image="test/protected"
        )
        track = Track.objects.create(
            title="Protected track", slug="protected-track"
        )
        self.client.force_login(self.staff)

        protected_posts = (
            ("/portal/gallery/upload/", {"title": "Unauthorized", "image": ""}),
            (f"/portal/gallery/{gallery.pk}/edit/", {"title": "Changed"}),
            (f"/portal/gallery/{gallery.pk}/publish/", {}),
            (f"/portal/gallery/{gallery.pk}/delete/", {"confirm_delete": "1"}),
            ("/portal/music/categories/add/", {"name": "Unauthorized"}),
            (f"/portal/music/track/{track.pk}/edit/", {"title": "Changed"}),
            (f"/portal/music/track/{track.pk}/delete/", {"confirm_delete": "1"}),
            ("/portal/biographies/add/", {"title": "Unauthorized", "body": "No"}),
            ("/portal/site-settings/", {"site_name": "Unauthorized"}),
        )
        for path, data in protected_posts:
            with self.subTest(path=path):
                response = self.client.post(path, data)
                self.assertEqual(response.status_code, 302)

        gallery.refresh_from_db()
        track.refresh_from_db()
        self.assertEqual(gallery.title, "Protected gallery image")
        self.assertTrue(gallery.is_published)
        self.assertEqual(track.title, "Protected track")
        self.assertFalse(Biography.objects.filter(title="Unauthorized").exists())

    def test_anonymous_delete_is_redirected_and_confirmation_is_required(self):
        image = GalleryImage.objects.create(title="Confirm me", image="test/confirm")
        self.client.logout()
        response = self.client.post(
            f"/portal/gallery/{image.pk}/delete/",
            {"confirm_delete": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GalleryImage.objects.filter(pk=image.pk).exists())

    def test_csrf_is_required_for_destructive_content_actions(self):
        image = GalleryImage.objects.create(title="CSRF protected", image="test/csrf")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.superadmin)

        response = csrf_client.post(
            f"/portal/gallery/{image.pk}/delete/",
            {"confirm_delete": "1"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(GalleryImage.objects.filter(pk=image.pk).exists())

        self.client.force_login(self.superadmin)
        response = self.client.post(f"/portal/gallery/{image.pk}/delete/", {})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GalleryImage.objects.filter(pk=image.pk).exists())

    def test_publish_endpoint_requires_post(self):
        image = GalleryImage.objects.create(
            title="Draft image", image="test/draft", is_published=False
        )
        response = self.client.get(f"/portal/gallery/{image.pk}/publish/")
        self.assertEqual(response.status_code, 405)
        image.refresh_from_db()
        self.assertFalse(image.is_published)
