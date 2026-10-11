from django.test import TestCase

from .models import GalleryCategory, GalleryImage


class GalleryCategoryTest(TestCase):
    def test_create_category_auto_slug(self):
        cat = GalleryCategory.objects.create(name="Events")
        self.assertEqual(cat.slug, "events")


class GalleryImageTest(TestCase):
    def test_create_image(self):
        # image field is a CloudinaryField; use a dummy public_id string.
        img = GalleryImage.objects.create(title="Stage Setup", image="sample/image.jpg")
        self.assertTrue(img.is_published)
        self.assertEqual(str(img), "Stage Setup")
