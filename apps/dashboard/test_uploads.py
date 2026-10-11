from io import BytesIO
from unittest.mock import patch

from cloudinary import CloudinaryResource
from cloudinary.exceptions import Error as CloudinaryError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from apps.dashboard.forms import GalleryImageForm, MixForm, TrackForm, VideoForm
from apps.core.models import SiteSettings
from apps.gallery.models import GalleryImage
from apps.music.models import Mix, Track
from apps.videos.models import Video
from config.cloudinary import cloudinary_configuration, missing_cloudinary_settings


def make_image_upload(name="stage.png", image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="purple").save(buffer, format=image_format)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type="image/png" if image_format == "PNG" else "image/jpeg",
    )


def make_audio_upload(name="track.mp3"):
    return SimpleUploadedFile(
        name,
        b"ID3" + b"\x00" * 32,
        content_type="audio/mpeg",
    )


def make_video_upload(name="live.mp4"):
    return SimpleUploadedFile(
        name,
        b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 24,
        content_type="video/mp4",
    )


class CloudinaryConfigurationTests(TestCase):
    def test_missing_configuration_is_reported_without_values(self):
        configuration = cloudinary_configuration({})

        self.assertEqual(
            missing_cloudinary_settings(configuration),
            (
                "CLOUDINARY_CLOUD_NAME",
                "CLOUDINARY_API_KEY",
                "CLOUDINARY_API_SECRET",
            ),
        )

    def test_cloudinary_url_is_supported_without_exposing_its_values(self):
        configuration = cloudinary_configuration(
            {"CLOUDINARY_URL": "cloudinary://api%2Fkey:secret%2Fvalue@sample-cloud"}
        )

        self.assertEqual(missing_cloudinary_settings(configuration), ())
        self.assertEqual(configuration["CLOUD_NAME"], "sample-cloud")
        self.assertEqual(configuration["API_KEY"], "api/key")
        self.assertEqual(configuration["API_SECRET"], "secret/value")

    def test_explicit_variables_override_url_values(self):
        configuration = cloudinary_configuration(
            {
                "CLOUDINARY_URL": "cloudinary://url-key:url-secret@url-cloud",
                "CLOUDINARY_CLOUD_NAME": "explicit-cloud",
                "CLOUDINARY_API_KEY": "explicit-key",
                "CLOUDINARY_API_SECRET": "explicit-secret",
            }
        )

        self.assertEqual(
            configuration,
            {
                "CLOUD_NAME": "explicit-cloud",
                "API_KEY": "explicit-key",
                "API_SECRET": "explicit-secret",
            },
        )


class UploadFormTests(TestCase):
    def test_gallery_minimum_fields_use_model_publication_default(self):
        form = GalleryImageForm(
            {"title": "Stage setup"},
            {"image": make_image_upload()},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data["is_published"])
        self.assertFalse(form.cleaned_data["is_featured"])
        self.assertEqual(form.cleaned_data["order"], 0)

    def test_track_minimum_fields_are_valid_and_draft_by_default(self):
        form = TrackForm(
            {"title": "Dance all night"},
            {"audio_file": make_audio_upload()},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["is_published"])
        self.assertFalse(form.cleaned_data["is_featured"])
        self.assertEqual(form.cleaned_data["description"], "")

    def test_duplicate_track_titles_receive_unique_slugs(self):
        Track.objects.create(title="Same title", slug="same-title")
        form = TrackForm(
            {"title": "Same title"},
            {"audio_file": make_audio_upload("same.mp3")},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.slug, "same-title-2")

    def test_mix_minimum_fields_require_audio_and_remain_unpublished(self):
        missing_audio = MixForm({"title": "Night mix"}, {})
        valid = MixForm(
            {"title": "Night mix"},
            {"audio_file": make_audio_upload("night.mp3")},
        )

        self.assertFalse(missing_audio.is_valid())
        self.assertIn("audio_file", missing_audio.errors)
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(valid.cleaned_data["is_published"])

    def test_video_minimum_fields_require_valid_video_and_remain_unpublished(self):
        form = VideoForm(
            {"title": "Live set"},
            {"video_file": make_video_upload()},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["is_published"])
        self.assertFalse(form.cleaned_data["is_featured"])

    def test_rejects_mismatched_image_and_audio_files(self):
        image_form = GalleryImageForm(
            {"title": "Not an image"},
            {
                "image": SimpleUploadedFile(
                    "not-an-image.png", b"not an image", content_type="image/png"
                )
            },
        )
        audio_form = TrackForm(
            {"title": "Not audio"},
            {
                "audio_file": SimpleUploadedFile(
                    "not-audio.mp3", b"not audio", content_type="audio/mpeg"
                )
            },
        )

        self.assertFalse(image_form.is_valid())
        self.assertIn("image", image_form.errors)
        self.assertFalse(audio_form.is_valid())
        self.assertIn("audio_file", audio_form.errors)

    def test_rejects_video_with_non_video_contents(self):
        form = VideoForm(
            {"title": "Not video"},
            {
                "video_file": SimpleUploadedFile(
                    "not-video.mp4", b"not video", content_type="video/mp4"
                )
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("video_file", form.errors)

    def test_rejects_image_over_size_limit(self):
        form = GalleryImageForm(
            {"title": "Large upload"},
            {
                "image": SimpleUploadedFile(
                    "large.png", b"x" * (10 * 1024 * 1024 + 1), content_type="image/png"
                )
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("too large", str(form.errors["image"]))

    def test_explicitly_unchecked_gallery_publication_is_kept_as_draft(self):
        form = GalleryImageForm(
            {"_portal_upload_form": "1", "title": "Private image"},
            {"image": make_image_upload("private.png")},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["is_published"])


class PortalUploadViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="upload_staff",
            email="upload@example.com",
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch("cloudinary.models.uploader.upload_resource")
    def test_gallery_upload_succeeds_with_mocked_cloudinary(self, upload_resource):
        upload_resource.return_value = CloudinaryResource(
            public_id="test/gallery/stage", format="png", resource_type="image"
        )

        response = self.client.post(
            "/portal/gallery/upload/",
            {"title": "Stage setup", "image": make_image_upload()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/gallery/")
        image = GalleryImage.objects.get(title="Stage setup")
        self.assertEqual(str(image.image), "test/gallery/stage")
        self.assertEqual(upload_resource.call_args.kwargs["resource_type"], "image")

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch("cloudinary.models.uploader.upload_resource")
    def test_track_upload_succeeds_and_keeps_raw_audio_type(self, upload_resource):
        upload_resource.return_value = CloudinaryResource(
            public_id="test/music/track", format="mp3", resource_type="raw"
        )

        response = self.client.post(
            "/portal/music/track/add/",
            {"title": "Dance all night", "audio_file": make_audio_upload()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/music/")
        self.assertTrue(Track.objects.filter(title="Dance all night").exists())
        self.assertEqual(upload_resource.call_args.kwargs["resource_type"], "raw")

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch("cloudinary.models.uploader.upload_resource")
    def test_video_upload_succeeds_with_video_resource_type(self, upload_resource):
        upload_resource.return_value = CloudinaryResource(
            public_id="test/videos/live", format="mp4", resource_type="video"
        )

        response = self.client.post(
            "/portal/videos/add/",
            {"title": "Live set", "video_file": make_video_upload()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/videos/")
        self.assertTrue(Video.objects.filter(title="Live set").exists())
        self.assertEqual(upload_resource.call_args.kwargs["resource_type"], "video")

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch("cloudinary.models.uploader.upload_resource")
    def test_mix_upload_succeeds_with_mocked_cloudinary(self, upload_resource):
        upload_resource.return_value = CloudinaryResource(
            public_id="test/music/mix", format="mp3", resource_type="raw"
        )

        response = self.client.post(
            "/portal/music/mix/add/",
            {"title": "Night mix", "audio_file": make_audio_upload("mix.mp3")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/music/")
        self.assertTrue(Mix.objects.filter(title="Night mix").exists())

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch(
        "cloudinary.models.uploader.upload_resource",
        side_effect=CloudinaryError("simulated upload failure"),
    )
    def test_cloudinary_failure_renders_error_without_saving_record(self, upload_resource):
        response = self.client.post(
            "/portal/gallery/upload/",
            {"title": "Failed upload", "image": make_image_upload("failed.png")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "upload could not be completed")
        self.assertFalse(GalleryImage.objects.filter(title="Failed upload").exists())
        upload_resource.assert_called_once()

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch(
        "cloudinary.models.uploader.upload_resource",
        side_effect=ValueError("Must supply api_key"),
    )
    def test_missing_api_key_error_is_handled_without_saving_record(self, upload_resource):
        response = self.client.post(
            "/portal/gallery/upload/",
            {"title": "Missing API key", "image": make_image_upload("missing-key.png")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "upload could not be completed")
        self.assertFalse(GalleryImage.objects.filter(title="Missing API key").exists())
        upload_resource.assert_called_once()

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch("apps.dashboard.views.uploader.destroy")
    @patch("cloudinary.models.uploader.upload_resource")
    def test_partial_remote_upload_is_cleaned_when_later_file_fails(
        self, upload_resource, destroy
    ):
        upload_resource.side_effect = [
            CloudinaryResource(
                public_id="test/music/cover", format="png", resource_type="image"
            ),
            CloudinaryError("simulated audio upload failure"),
        ]

        response = self.client.post(
            "/portal/music/mix/add/",
            {
                "title": "Partial mix",
                "audio_file": make_audio_upload("partial.mp3"),
                "cover_image": make_image_upload("partial.png"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "upload could not be completed")
        self.assertFalse(Mix.objects.filter(title="Partial mix").exists())
        destroy.assert_called_once_with("test/music/cover", resource_type="image")

    @override_settings(CLOUDINARY_MISSING_SETTINGS=())
    @patch("cloudinary.models.uploader.upload_resource")
    def test_site_profile_image_upload_uses_validated_cloudinary_storage(
        self, upload_resource
    ):
        upload_resource.return_value = CloudinaryResource(
            public_id="test/site/profile", format="png", resource_type="image"
        )

        response = self.client.post(
            "/portal/site-settings/",
            {
                "site_name": "New site name",
                "profile_image": make_image_upload("profile.png"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/site-settings/")
        settings_obj = SiteSettings.objects.get(pk=1)
        self.assertEqual(settings_obj.site_name, "New site name")
        self.assertEqual(str(settings_obj.profile_image), "test/site/profile")

    def test_invalid_site_profile_image_preserves_entered_settings(self):
        response = self.client.post(
            "/portal/site-settings/",
            {
                "site_name": "Keep this site name",
                "profile_image": SimpleUploadedFile("profile.png", b"not an image"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keep this site name")
        self.assertContains(response, "Choose a valid image file.")
        self.assertFalse(SiteSettings.objects.filter(site_name="Keep this site name").exists())

    @override_settings(
        CLOUDINARY_MISSING_SETTINGS=("CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    )
    @patch("cloudinary.models.uploader.upload_resource")
    def test_missing_credentials_gives_setup_instructions_without_uploading(
        self, upload_resource
    ):
        response = self.client.post(
            "/portal/gallery/upload/",
            {"title": "Unconfigured upload", "image": make_image_upload("local.png")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cloudinary is not configured")
        self.assertContains(response, "CLOUDINARY_API_KEY")
        self.assertFalse(GalleryImage.objects.filter(title="Unconfigured upload").exists())
        upload_resource.assert_not_called()

    def test_invalid_upload_keeps_title_and_shows_validation_error(self):
        response = self.client.post(
            "/portal/gallery/upload/",
            {
                "title": "Keep this title",
                "image": SimpleUploadedFile("broken.png", b"not image"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keep this title")
        self.assertContains(response, "Choose a valid image file.")
        self.assertFalse(GalleryImage.objects.filter(title="Keep this title").exists())

    def test_upload_pages_require_staff_authentication(self):
        self.client.logout()

        for path in (
            "/portal/gallery/upload/",
            "/portal/music/track/add/",
            "/portal/music/mix/add/",
            "/portal/videos/add/",
            "/portal/music/mix/sample/edit/",
            "/portal/site-settings/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/portal/login/", response["Location"])
                post_response = self.client.post(path, {})
                self.assertEqual(post_response.status_code, 302)
                self.assertIn("/portal/login/", post_response["Location"])

    def test_content_upload_pages_render_for_staff(self):
        for path in (
            "/portal/gallery/upload/",
            "/portal/music/mix/add/",
            "/portal/music/track/add/",
            "/portal/videos/add/",
            "/portal/site-settings/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'enctype="multipart/form-data"')
