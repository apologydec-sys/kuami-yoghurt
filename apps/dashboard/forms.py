import os

from django import forms
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from apps.bookings.models import BOOKING_STATUSES
from apps.core.models import Biography, SiteSettings
from apps.gallery.models import GalleryCategory, GalleryImage
from apps.music.models import Category, Mix, Track
from apps.videos.models import Video, VideoCategory


class QuotationForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label="Amount",
        widget=forms.NumberInput(attrs={"placeholder": "0.00", "step": "0.01"}),
    )
    currency = forms.CharField(
        max_length=10,
        initial="GHS",
        label="Currency",
        widget=forms.TextInput(attrs={"placeholder": "GHS"}),
    )
    details = forms.CharField(
        max_length=5000,
        required=False,
        label="Quotation Details",
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "What is included…"}),
    )
    terms = forms.CharField(
        max_length=5000,
        required=False,
        label="Terms and Conditions",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Payment terms, cancellation policy…"}),
    )
    expires_at = forms.DateTimeField(
        required=False,
        label="Expiry Date/Time (optional)",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )


class BookingStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=BOOKING_STATUSES,
        label="New Status",
    )
    note = forms.CharField(
        max_length=2000,
        required=False,
        label="Internal Note",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note about this status change…"}),
    )


class InternalNoteForm(forms.Form):
    internal_notes = forms.CharField(
        max_length=10000,
        required=False,
        label="Internal Notes",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Private notes visible only to admin…"}),
    )


class PublicationModelFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        for field_name in ("order", "duration_seconds"):
            if field_name in self.fields and cleaned_data.get(field_name) is None:
                cleaned_data[field_name] = self._meta.model._meta.get_field(
                    field_name
                ).get_default()
        if (
            self.is_bound
            and self.instance.pk
            and not self.data.get("_advanced_settings")
        ):
            for field_name in getattr(self, "advanced_field_names", ()):
                if field_name in self.fields:
                    cleaned_data[field_name] = getattr(self.instance, field_name)
        elif (
            self.is_bound
            and "is_published" in self.fields
            and not self.data.get("_advanced_settings")
        ):
            cleaned_data["is_published"] = self._meta.model._meta.get_field(
                "is_published"
            ).get_default()
        elif (
            self.is_bound
            and "is_published" in self.fields
            and self.data.get("_advanced_settings")
            and "is_published" not in self.data
        ):
            cleaned_data["is_published"] = False
        model_field_names = {
            field.name for field in self._meta.model._meta.fields
        }
        if (
            not self.instance.pk
            and "slug" in model_field_names
            and "slug" not in self.fields
            and cleaned_data.get("title")
        ):
            base_slug = slugify(cleaned_data["title"]) or self._meta.model._meta.model_name
            candidate_slug = base_slug
            suffix = 2
            while self._meta.model._default_manager.filter(
                slug=candidate_slug
            ).exists():
                candidate_slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.instance.slug = candidate_slug
        return cleaned_data


class GalleryImageForm(PublicationModelFormMixin, forms.ModelForm):
    basic_field_names = ("title", "description", "image")
    advanced_field_names = ("category", "is_published", "is_featured", "order")

    class Meta:
        model = GalleryImage
        fields = [
            "title", "description", "image", "category", "is_published",
            "is_featured", "order",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Image title"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional description"}),
            "order": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Title"
        self.fields["title"].help_text = "Give this image a short, clear title."
        self.fields["description"].help_text = "Optional. Add a short caption."
        self.fields["image"].label = "Image file"
        self.fields["image"].help_text = "JPEG, PNG, or WebP; up to 10 MB."
        self.fields["image"].validators.append(validate_image_upload)
        _configure_file_widget(self.fields["image"], "image/jpeg,image/png,image/webp", preview=True)
        self.fields["category"].required = False
        self.fields["order"].required = False
        self.fields["category"].help_text = "Optional gallery category."
        self.fields["is_published"].help_text = "Gallery images are published by default."

    @property
    def basic_fields(self):
        return [self[name] for name in self.basic_field_names]

    @property
    def advanced_fields(self):
        return [self[name] for name in self.advanced_field_names]


class UniqueCategorySlugFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        if name:
            slug = slugify(name)
            categories = self._meta.model._default_manager.filter(slug=slug)
            if self.instance.pk:
                categories = categories.exclude(pk=self.instance.pk)
            if categories.exists():
                self.add_error("name", "A category with this name already exists.")
        return cleaned_data


class GalleryCategoryForm(UniqueCategorySlugFormMixin, forms.ModelForm):
    class Meta:
        model = GalleryCategory
        fields = ["name", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].help_text = "Category names are shown in the public gallery."


class MusicCategoryForm(UniqueCategorySlugFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "order"]


class MixForm(PublicationModelFormMixin, forms.ModelForm):
    basic_field_names = ("title", "description", "audio_file", "cover_image")
    advanced_field_names = (
        "category", "duration_seconds", "tracklist", "is_published",
        "is_featured", "published_at",
    )

    class Meta:
        model = Mix
        fields = [
            "title", "description", "cover_image", "audio_file", "category",
            "duration_seconds", "is_published", "is_featured", "published_at",
            "tracklist",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Mix title"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "tracklist": forms.Textarea(attrs={"rows": 5, "placeholder": "Track 1\nTrack 2…"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Title"
        self.fields["title"].help_text = "Give this mix a short, clear title."
        self.fields["description"].help_text = "Optional. Describe the mix."
        _configure_audio_field(self.fields["audio_file"], self.instance)
        self.fields["cover_image"].label = "Cover artwork (optional)"
        self.fields["cover_image"].required = False
        self.fields["cover_image"].help_text = "JPEG, PNG, or WebP; up to 10 MB."
        self.fields["cover_image"].validators.append(validate_image_upload)
        _configure_file_widget(
            self.fields["cover_image"], "image/jpeg,image/png,image/webp", preview=True
        )
        self.fields["category"].required = False
        self.fields["duration_seconds"].required = False

    @property
    def basic_fields(self):
        return [self[name] for name in self.basic_field_names]

    @property
    def advanced_fields(self):
        return [self[name] for name in self.advanced_field_names]


class TrackForm(PublicationModelFormMixin, forms.ModelForm):
    basic_field_names = ("title", "description", "audio_file", "cover_image")
    advanced_field_names = (
        "mix", "category", "duration_seconds", "is_published",
        "is_featured", "published_at",
    )

    class Meta:
        model = Track
        fields = [
            "title", "description", "cover_image", "audio_file", "mix",
            "category", "duration_seconds", "is_published", "is_featured",
            "published_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Track title"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Track title"
        self.fields["title"].help_text = "Give this track a short, clear title."
        self.fields["description"].help_text = "Optional. Describe the track."
        _configure_audio_field(self.fields["audio_file"], self.instance)
        self.fields["cover_image"].label = "Cover artwork (optional)"
        self.fields["cover_image"].required = False
        self.fields["cover_image"].help_text = "JPEG, PNG, or WebP; up to 10 MB."
        self.fields["cover_image"].validators.append(validate_image_upload)
        _configure_file_widget(
            self.fields["cover_image"], "image/jpeg,image/png,image/webp", preview=True
        )
        self.fields["mix"].required = False
        self.fields["category"].required = False
        self.fields["duration_seconds"].required = False

    @property
    def basic_fields(self):
        return [self[name] for name in self.basic_field_names]

    @property
    def advanced_fields(self):
        return [self[name] for name in self.advanced_field_names]


class VideoForm(PublicationModelFormMixin, forms.ModelForm):
    basic_field_names = ("title", "description", "video_file", "thumbnail")
    advanced_field_names = (
        "category", "is_published", "is_featured", "published_at",
        "duration_seconds",
    )

    class Meta:
        model = Video
        fields = [
            "title", "description", "video_file", "thumbnail", "category",
            "is_published", "is_featured", "published_at",
            "duration_seconds",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Video title"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Title"
        self.fields["title"].help_text = "Give this video a short, clear title."
        self.fields["description"].help_text = "Optional. Describe the video."
        self.fields["video_file"].label = "Video file"
        self.fields["video_file"].required = not self.instance.video_file
        self.fields["video_file"].help_text = "MP4, MOV, WebM, AVI, or MKV; up to 500 MB."
        self.fields["video_file"].validators.append(validate_video_upload)
        _configure_file_widget(
            self.fields["video_file"],
            "video/mp4,video/quicktime,video/webm,video/x-msvideo,video/x-matroska",
        )
        self.fields["thumbnail"].label = "Thumbnail (optional)"
        self.fields["thumbnail"].required = False
        self.fields["thumbnail"].help_text = "JPEG, PNG, or WebP; up to 10 MB."
        self.fields["thumbnail"].validators.append(validate_image_upload)
        _configure_file_widget(
            self.fields["thumbnail"], "image/jpeg,image/png,image/webp", preview=True
        )
        self.fields["category"].required = False
        self.fields["duration_seconds"].required = False

    @property
    def basic_fields(self):
        return [self[name] for name in self.basic_field_names]

    @property
    def advanced_fields(self):
        return [self[name] for name in self.advanced_field_names]


class VideoCategoryForm(UniqueCategorySlugFormMixin, forms.ModelForm):
    class Meta:
        model = VideoCategory
        fields = ["name", "order"]


class BiographyForm(forms.ModelForm):
    class Meta:
        model = Biography
        fields = ["title", "body", "profile_image", "is_published"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile_image"].required = False
        self.fields["profile_image"].validators.append(validate_image_upload)
        self.fields["profile_image"].widget.attrs.update(
            {
                "accept": "image/jpeg,image/png,image/webp",
                "data-upload-input": "",
                "data-upload-preview": "",
            }
        )


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "site_name", "tagline", "about_text", "biography", "profile_image",
            "whatsapp_number", "email", "facebook_url", "instagram_url",
            "twitter_url", "youtube_url",
        ]
        widgets = {
            "about_text": forms.Textarea(attrs={"rows": 3}),
            "biography": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile_image"].label = "Profile image"
        self.fields["profile_image"].required = False
        self.fields["profile_image"].help_text = "Optional JPEG, PNG, or WebP image; up to 10 MB."
        self.fields["profile_image"].validators.append(validate_image_upload)
        _configure_file_widget(
            self.fields["profile_image"], "image/jpeg,image/png,image/webp", preview=True
        )


def _configure_audio_field(field, instance):
    field.label = "Audio file"
    field.required = not instance.pk or not bool(instance.audio_file)
    field.help_text = "MP3, WAV, FLAC, OGG, M4A, or AAC; up to 100 MB."
    field.validators.append(validate_audio_upload)
    _configure_file_widget(
        field,
        "audio/mpeg,audio/wav,audio/flac,audio/ogg,audio/mp4,audio/aac",
    )


def _configure_file_widget(field, accept, preview=False):
    field.widget.attrs.update(
        {
            "accept": accept,
            "data-upload-input": "",
        }
    )
    if preview:
        field.widget.attrs["data-upload-preview"] = ""


def _validate_file_size(uploaded_file, maximum_size):
    if uploaded_file.size > maximum_size:
        raise forms.ValidationError("This file is too large.")


def validate_image_upload(uploaded_file):
    _validate_file_size(uploaded_file, 10 * 1024 * 1024)
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    expected_formats = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
    }
    if extension not in expected_formats:
        raise forms.ValidationError("Choose a JPEG, PNG, or WebP image.")
    try:
        with Image.open(uploaded_file) as image:
            if image.format != expected_formats[extension]:
                raise forms.ValidationError(
                    "The image contents do not match the selected file type."
                )
            if image.width * image.height > 40_000_000:
                raise forms.ValidationError("This image has too many pixels.")
            image.verify()
    except forms.ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise forms.ValidationError("Choose a valid image file.") from exc
    finally:
        uploaded_file.seek(0)


def _has_audio_signature(header, extension):
    if extension == ".mp3":
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        )
    if extension == ".wav":
        return header.startswith(b"RIFF") and header[8:12] == b"WAVE"
    if extension == ".flac":
        return header.startswith(b"fLaC")
    if extension == ".ogg":
        return header.startswith(b"OggS")
    if extension == ".m4a":
        return header[4:8] == b"ftyp"
    if extension == ".aac":
        return len(header) >= 2 and header[0] == 0xFF and header[1] & 0xF6 == 0xF0
    return False


def validate_audio_upload(uploaded_file):
    _validate_file_size(uploaded_file, 100 * 1024 * 1024)
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    allowed_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
    if extension not in allowed_extensions:
        raise forms.ValidationError("Choose a supported audio file.")
    header = uploaded_file.read(16)
    uploaded_file.seek(0)
    if not _has_audio_signature(header, extension):
        raise forms.ValidationError("The audio contents do not match the selected file type.")


def validate_video_upload(uploaded_file):
    _validate_file_size(uploaded_file, 500 * 1024 * 1024)
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    header = uploaded_file.read(16)
    uploaded_file.seek(0)
    valid_signature = (
        (extension in {".mp4", ".m4v", ".mov"} and header[4:8] == b"ftyp")
        or (extension in {".webm", ".mkv"} and header.startswith(b"\x1a\x45\xdf\xa3"))
        or (extension == ".avi" and header.startswith(b"RIFF") and header[8:12] == b"AVI ")
    )
    if not valid_signature:
        raise forms.ValidationError(
            "Choose a supported MP4, MOV, WebM, AVI, or MKV video file."
        )
