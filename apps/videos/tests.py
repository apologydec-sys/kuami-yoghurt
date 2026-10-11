from django.test import TestCase

from .models import Video, VideoCategory


class VideoCategoryTest(TestCase):
    def test_create_category_auto_slug(self):
        cat = VideoCategory.objects.create(name="Live Sets")
        self.assertEqual(cat.slug, "live-sets")


class VideoTest(TestCase):
    def test_create_video(self):
        video = Video.objects.create(title="Club Night 2024", slug="club-night-2024")
        self.assertFalse(video.is_published)
        self.assertEqual(video.play_count, 0)
        self.assertEqual(str(video), "Club Night 2024")

    def test_auto_slug(self):
        video = Video.objects.create(title="Festival Mix")
        self.assertEqual(video.slug, "festival-mix")
