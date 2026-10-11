from django.test import TestCase

from .models import Category, Mix, Track


class CategoryTest(TestCase):
    def test_create_category_auto_slug(self):
        cat = Category.objects.create(name="Afrobeats")
        self.assertEqual(cat.slug, "afrobeats")

    def test_str(self):
        cat = Category.objects.create(name="Hip Hop", slug="hip-hop")
        self.assertEqual(str(cat), "Hip Hop")


class MixTest(TestCase):
    def test_create_mix(self):
        mix = Mix.objects.create(title="Summer Vibes Vol 1", slug="summer-vibes-vol-1")
        self.assertFalse(mix.is_published)
        self.assertEqual(mix.play_count, 0)

    def test_auto_slug(self):
        mix = Mix.objects.create(title="Night Mix")
        self.assertEqual(mix.slug, "night-mix")


class TrackTest(TestCase):
    def test_create_track(self):
        track = Track.objects.create(title="Dance All Night", slug="dance-all-night")
        self.assertFalse(track.is_published)
        self.assertEqual(str(track), "Dance All Night")
