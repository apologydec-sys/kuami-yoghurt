# Implementation Plan — DJ Kuami Yoghurt Platform

This plan is organised into four phases. Each phase must leave the codebase in a buildable, testable state. All commands are Windows PowerShell. Run from `c:\Users\Akanni-kweku\DJKuamiYoghurt`. Venv Python: `.venv\Scripts\python.exe`.

---

## Key Design Decisions

**App packaging**: All apps live under `apps/` and are registered as `apps.core`, `apps.music`, etc. — this avoids name collisions with third-party packages.

**Cloudinary fields**: Use `cloudinary.models.CloudinaryField` (confirmed importable). For audio/video, pass `resource_type='raw'` or `resource_type='video'` to CloudinaryField so Cloudinary handles the correct upload pipeline.

**Booking tokens**: Use `secrets.token_urlsafe(48)` — 48 bytes of entropy → 64-character URL-safe string. Store with `db_index=True`. Never log tokens. Tracking URLs look like `/bookings/booking/<token>/` — token is not guessable.

**Chat**: Polling only (no WebSockets, despite channels being installed). Poll endpoint `GET /chat/<pk>/poll/?since=<ISO-timestamp>` returns JSON. JS polls every 3 seconds.

**Dashboard**: Uses Django's built-in `login_required` + `request.user.is_staff` check, not a new auth system. Custom templates, not Django admin.

**Static files**: Source in `static/`, output from collectstatic in `staticfiles/`. WhiteNoise serves `staticfiles/` in production. `STATICFILES_DIRS = [BASE_DIR / 'static']` must be added to settings.

**Media in dev**: `MEDIA_URL = '/media/'` + `MEDIA_ROOT = BASE_DIR / 'media'` for local dev. In production, all media goes to Cloudinary.

**No extra pip packages needed**: All required packages (Django, cloudinary, django-cloudinary-storage, whitenoise, gunicorn, pillow, requests, channels) are already installed.

**Django 5.2 gotcha**: `STATICFILES_STORAGE` is deprecated — already handled via `STORAGES` dict. Do not add `STATICFILES_STORAGE` again.

**`STATICFILES_STORAGE` duplicate**: settings.py currently has both `STATICFILES_STORAGE = "whitenoise.storage.StaticFilesStorage"` (deprecated key) AND the correct `STORAGES` dict. The deprecated key should be removed to silence Django 5.2 warnings.

---

## Phase 1 — App Skeletons, Models, Migrations (FEAT-001)

- [ ] 1. **Remove deprecated `STATICFILES_STORAGE` key from `config/settings.py`**. Add `STATICFILES_DIRS = [BASE_DIR / 'static']`, `MEDIA_URL = '/media/'`, `MEDIA_ROOT = BASE_DIR / 'media'`, `LOGIN_URL = '/accounts/login/'`, `LOGIN_REDIRECT_URL = '/dashboard/'`, `LOGOUT_REDIRECT_URL = '/'`. Add `'apps.core.context_processors.site_settings'` to `TEMPLATES[0]['OPTIONS']['context_processors']`.
      Files: `config/settings.py`
      Verify: `.venv\Scripts\python.exe manage.py check`

- [ ] 2. **Create `apps/core/`** with `__init__.py`, `apps.py` (AppConfig name=`apps.core`), `models.py` (SiteSettings, ContactMessage, Biography), `admin.py`, `migrations/__init__.py`.
      SiteSettings fields: `site_name`, `tagline`, `about_text TextField`, `profile_image CloudinaryField(blank=True)`, `whatsapp_number`, `email`, `facebook_url`, `instagram_url`, `twitter_url`, `youtube_url`, `is_active BooleanField`.
      ContactMessage fields: `name`, `email`, `phone(blank=True)`, `subject`, `message TextField`, `ip_address(blank=True)`, `created_at auto_now_add`, `is_read BooleanField default=False`.
      Files: `apps/core/__init__.py`, `apps/core/apps.py`, `apps/core/models.py`, `apps/core/admin.py`, `apps/core/migrations/__init__.py`
      Verify: `.venv\Scripts\python.exe manage.py check` (app not yet in INSTALLED_APPS — add it in step 8)

- [ ] 3. **Create `apps/music/`** with `__init__.py`, `apps.py`, `models.py`, `admin.py`, `migrations/__init__.py`.
      Models: `Category(name, slug auto, description, order IntegerField default=0)`; `Mix(title, slug, description, cover_image CloudinaryField blank=True, audio_file CloudinaryField(resource_type='raw'), category FK Category null=True, duration_seconds PositiveIntegerField null=True, is_published bool, is_featured bool, published_at DateTimeField null=True, tracklist TextField blank=True, play_count PositiveIntegerField default=0, created_at, updated_at)`; `Track(title, slug, description, cover_image CloudinaryField blank=True, audio_file CloudinaryField(resource_type='raw'), mix FK Mix null=True blank=True, category FK Category null=True, duration_seconds null=True, is_published, is_featured, published_at null=True, play_count default=0, created_at, updated_at)`.
      Files: `apps/music/__init__.py`, `apps/music/apps.py`, `apps/music/models.py`, `apps/music/admin.py`, `apps/music/migrations/__init__.py`

- [ ] 4. **Create `apps/videos/`** with `__init__.py`, `apps.py`, `models.py`, `admin.py`, `migrations/__init__.py`.
      Models: `VideoCategory(name, slug, order)`; `Video(title, slug, description, video_file CloudinaryField(resource_type='video'), thumbnail CloudinaryField blank=True, category FK null=True, is_published, is_featured, published_at null=True, duration_seconds null=True, play_count default=0, created_at, updated_at)`.
      Files: `apps/videos/__init__.py`, `apps/videos/apps.py`, `apps/videos/models.py`, `apps/videos/admin.py`, `apps/videos/migrations/__init__.py`

- [ ] 5. **Create `apps/gallery/`** with `__init__.py`, `apps.py`, `models.py`, `admin.py`, `migrations/__init__.py`.
      Models: `GalleryCategory(name, slug, order)`; `GalleryImage(title, description blank=True, image CloudinaryField, category FK null=True, is_published bool default=True, is_featured bool default=False, order IntegerField default=0, created_at, updated_at)`.
      Files: `apps/gallery/__init__.py`, `apps/gallery/apps.py`, `apps/gallery/models.py`, `apps/gallery/admin.py`, `apps/gallery/migrations/__init__.py`

- [ ] 6. **Create `apps/bookings/`** with `__init__.py`, `apps.py`, `models.py`, `admin.py`, `migrations/__init__.py`.
      Constants: `EVENT_TYPE_CHOICES` and `BOOKING_STATUS_CHOICES` as module-level tuples.
      Models: `Booking(reference UUIDField default=uuid4 unique, token CharField(64) unique db_index=True, customer_name, customer_email, customer_phone, event_type choices, event_date DateField, event_time TimeField null=True, event_location, guest_count PositiveIntegerField null=True, music_preferences TextField blank=True, additional_requirements TextField blank=True, status CharField choices default='received', internal_notes TextField blank=True, created_at, updated_at, ip_address blank=True)`; `Quotation(booking OneToOneField Booking related_name='quotation', amount DecimalField(10,2), currency CharField default='GHS', details TextField, terms TextField blank=True, expires_at DateTimeField null=True, created_at, updated_at)`; `BookingStatusHistory(booking FK, status, changed_by FK settings.AUTH_USER_MODEL null=True blank=True on_delete=SET_NULL, note TextField blank=True, changed_at auto_now_add)`; `BookingMessage(booking FK, message TextField, is_from_dj bool default=False, created_at auto_now_add)`.
      Files: `apps/bookings/__init__.py`, `apps/bookings/apps.py`, `apps/bookings/models.py`, `apps/bookings/admin.py`, `apps/bookings/migrations/__init__.py`

- [ ] 7. **Create `apps/chat/`** with `__init__.py`, `apps.py`, `models.py`, `admin.py`, `migrations/__init__.py`.
      Models: `Conversation(session_key CharField unique, customer_name, customer_email, customer_phone blank=True, booking FK apps.bookings.Booking null=True blank=True on_delete=SET_NULL, created_at, updated_at, is_archived bool default=False)`; `Message(conversation FK Conversation, content TextField max_length=2000, is_from_dj bool default=False, is_read bool default=False, created_at auto_now_add)`.
      Files: `apps/chat/__init__.py`, `apps/chat/apps.py`, `apps/chat/models.py`, `apps/chat/admin.py`, `apps/chat/migrations/__init__.py`

- [ ] 8. **Create `apps/dashboard/`** with `__init__.py`, `apps.py` (name=`apps.dashboard`), empty `admin.py`, empty `migrations/__init__.py`. No models.
      Files: `apps/dashboard/__init__.py`, `apps/dashboard/apps.py`, `apps/dashboard/admin.py`, `apps/dashboard/migrations/__init__.py`

- [ ] 9. **Add all 7 apps to `INSTALLED_APPS` in `config/settings.py`** in this exact order (after existing entries):
      `'apps.core'`, `'apps.music'`, `'apps.videos'`, `'apps.gallery'`, `'apps.bookings'`, `'apps.chat'`, `'apps.dashboard'`
      Files: `config/settings.py`
      Verify: `.venv\Scripts\python.exe manage.py check`

- [ ] 10. **Create template and static subdirectories** that are missing: `templates/videos/`, `templates/dashboard/`, `templates/errors/`. Static subdirectories `static/css/`, `static/js/`, `static/images/` already exist.
       Files: `templates/videos/.gitkeep`, `templates/dashboard/.gitkeep`, `templates/errors/.gitkeep`

- [ ] 11. **Run migrations** in dependency order. `bookings` depends on auth (for changed_by FK); `chat` depends on bookings.
       Commands: `.venv\Scripts\python.exe manage.py makemigrations core music videos gallery bookings chat` then `.venv\Scripts\python.exe manage.py migrate`
       Verify: `.venv\Scripts\python.exe manage.py showmigrations` — all 7 apps show `[X]` applied migrations

---

## Phase 2 — Views, Forms, URL Routing (FEAT-002)

- [ ] 12. **Create `apps/core/context_processors.py`** and `apps/core/forms.py`.
       Context processor: `site_settings(request)` returns `{'site_settings': SiteSettings.objects.first()}`.
       ContactForm: `name(max_length=200)`, `email EmailField`, `phone(required=False, max_length=20)`, `subject(max_length=200)`, `message(widget=Textarea, max_length=2000)`. Validate message not blank.
       Files: `apps/core/context_processors.py`, `apps/core/forms.py`

- [ ] 13. **Create `apps/core/views.py`** with `HomeView`, `AboutView`, `ContactView`, `ContactSuccessView`, `handler404`, `handler500`. HomeView: queries published featured mixes (limit 4), published featured tracks (limit 4), published featured videos (limit 3), published featured gallery images (limit 6), SiteSettings.objects.first(). ContactView: save ContactMessage on valid POST, record ip from `request.META.get('REMOTE_ADDR')`.
       Files: `apps/core/views.py`

- [ ] 14. **Create `apps/core/urls.py`** with `app_name = 'core'`. Paths: `''` → HomeView `name='home'`; `'about/'` → AboutView; `'contact/'` → ContactView; `'contact/success/'` → ContactSuccessView.
       Files: `apps/core/urls.py`

- [ ] 15. **Create `apps/music/forms.py`** and **`apps/music/views.py`**. SearchForm: `q CharField(required=False)`, `category ModelChoiceField(required=False)`. Views: `MixListView` (filter `is_published=True`, apply search/category filter, paginate by 12), `MixDetailView` (404 if not published, increment `play_count`), `TrackListView`, `TrackDetailView`, `PlayCountIncrementView` (POST-only JSON endpoint `{play_count}`).
       Files: `apps/music/forms.py`, `apps/music/views.py`

- [ ] 16. **Create `apps/music/urls.py`** with `app_name = 'music'`. Paths: `'mixes/'`, `'mixes/<slug:slug>/'`, `'tracks/'`, `'tracks/<slug:slug>/'`, `'mixes/<slug:slug>/play/'` → PlayCountIncrementView.
       Files: `apps/music/urls.py`

- [ ] 17. **Create `apps/videos/forms.py`**, **`apps/videos/views.py`**, **`apps/videos/urls.py`** with `app_name = 'videos'`. VideoListView filters `is_published=True`, supports `?category=<slug>`. VideoDetailView increments `play_count`. URL: `''` → list, `'<slug:slug>/'` → detail.
       Files: `apps/videos/forms.py`, `apps/videos/views.py`, `apps/videos/urls.py`

- [ ] 18. **Create `apps/gallery/views.py`**, **`apps/gallery/urls.py`** with `app_name = 'gallery'`. GalleryView: all `is_published=True` images, optional `?category=<slug>` filter. GalleryDetailView. URL: `''` → index, `'<int:pk>/'` → detail.
       Files: `apps/gallery/views.py`, `apps/gallery/urls.py`

- [ ] 19. **Create `apps/bookings/forms.py`**. BookingForm fields: `customer_name`, `customer_email EmailField`, `customer_phone`, `event_type ChoiceField`, `event_date DateField(widget=DateInput type=date)`, `event_time TimeField(required=False, widget=TimeInput type=time)`, `event_location`, `guest_count IntegerField(required=False, min_value=1, max_value=100000)`, `music_preferences Textarea(required=False)`, `additional_requirements Textarea(required=False)`. Custom `clean_event_date`: raise ValidationError if date is in the past.
       Files: `apps/bookings/forms.py`

- [ ] 20. **Create `apps/bookings/utils.py`** with `generate_token()` → `secrets.token_urlsafe(48)` and `generate_whatsapp_link(phone, message)` → URL-encoded `https://wa.me/{phone}?text={quote(message)}`.
       Files: `apps/bookings/utils.py`

- [ ] 21. **Create `apps/bookings/views.py`**. `BookingCreateView`: rate-limit using session (`last_booking_ts`), reject if < 60s since last. On valid POST: create Booking with `token=generate_token()`, create `BookingStatusHistory(status='received')`. Redirect to `bookings:success` with token. `BookingSuccessView`: get Booking by token (404 if missing). `BookingTrackingView`: get by token, render tracking page with quotation if exists. `QuotationResponseView`: POST-only, check `status == 'quotation_sent'`, update status to `'confirmed'` or `'declined'`, create history entry.
       Files: `apps/bookings/views.py`

- [ ] 22. **Create `apps/bookings/urls.py`** with `app_name = 'bookings'`. Paths: `'book/'`, `'book/success/<str:token>/'`, `'booking/<str:token>/'`, `'booking/<str:token>/respond/'`.
       Files: `apps/bookings/urls.py`

- [ ] 23. **Wire all app URLs into `config/urls.py`**. Import and include: core at `''`, music at `'music/'`, videos at `'videos/'`, gallery at `'gallery/'`, bookings at `'bookings/'`. Add `handler404`/`handler500` assignments. Add dev media serving block inside `if settings.DEBUG`.
       Files: `config/urls.py`
       Verify: `.venv\Scripts\python.exe manage.py check` ; `.venv\Scripts\python.exe manage.py test apps.core apps.bookings --verbosity=2`

- [ ] 24. **Write tests for Phase 2** in `apps/core/tests.py` and `apps/bookings/tests.py`. Core tests: home returns 200, contact form POST saves ContactMessage, invalid email rejected. Booking tests: valid form creates Booking + token, past date rejected, tracking view 200 with valid token, 404 with wrong token, quotation respond rejects wrong status.
       Files: `apps/core/tests.py`, `apps/bookings/tests.py`
       Verify: `.venv\Scripts\python.exe manage.py test apps.core apps.bookings --verbosity=2`

---

## Phase 3 — Chat, Dashboard, Templates, Static Assets (FEAT-003)

- [ ] 25. **Create `apps/chat/forms.py`** and **`apps/chat/views.py`**. Forms: `StartConversationForm(customer_name, customer_email, customer_phone optional, initial_message Textarea max_length=2000)`, `MessageForm(content Textarea max_length=2000)`. Views: `ChatStartView`, `ChatWindowView` (verify `session_key == request.session.session_key`, 403 otherwise), `SendMessageView` (POST-only, returns JSON), `PollMessagesView` (GET, `?since=<ISO>`, returns JSON list).
       Files: `apps/chat/forms.py`, `apps/chat/views.py`

- [ ] 26. **Create `apps/chat/urls.py`** with `app_name = 'chat'`. Paths: `'chat/'`, `'chat/<int:pk>/'`, `'chat/<int:pk>/send/'`, `'chat/<int:pk>/poll/'`. Add to `config/urls.py` at `''` prefix.
       Files: `apps/chat/urls.py`; update `config/urls.py`

- [ ] 27. **Create `apps/dashboard/forms.py`** and **`apps/dashboard/views.py`**. All views decorated with `@login_required` and guarded with `if not request.user.is_staff: return HttpResponseForbidden()`. Views listed in FEAT-003 step 4. Forms: QuotationForm, BookingStatusForm, InternalNoteForm, GalleryImageForm, MixForm (title, slug, description, cover_image, audio_file, category, duration_seconds, is_published, is_featured, tracklist), TrackForm, VideoForm.
       Files: `apps/dashboard/forms.py`, `apps/dashboard/views.py`

- [ ] 28. **Create `apps/dashboard/urls.py`** with `app_name = 'dashboard'`. Add to `config/urls.py` at `'dashboard/'`. Include `path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login')` and `path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout')` at root level in `config/urls.py`.
       Files: `apps/dashboard/urls.py`; update `config/urls.py`

- [ ] 29. **Create `templates/base.html`** — dark-themed HTML5 base with CSS variables, responsive nav (hamburger on mobile), footer, Django messages, `{% block content %}`, links to `/static/css/main.css` and `/static/js/main.js`. Nav links: Home, Music, Videos, Gallery, Book Now. Footer: social links from `{{ site_settings }}` context, WhatsApp float button.
       Files: `templates/base.html`

- [ ] 30. **Create `templates/core/` templates**: `home.html`, `about.html`, `contact.html`, `contact_success.html`. Home: hero (`<section class="hero">`), featured mixes section (empty state if none), tracks section, videos section, gallery strip, booking CTA. All dynamic content from context.
       Files: `templates/core/home.html`, `templates/core/about.html`, `templates/core/contact.html`, `templates/core/contact_success.html`

- [ ] 31. **Create `templates/music/` templates**: `mix_list.html`, `mix_detail.html` (HTML5 `<audio>` player), `track_list.html`, `track_detail.html` (HTML5 `<audio>` player). Audio player markup: `<audio id="audio-player" src="{{ mix.audio_file.url }}" preload="metadata">`, custom controls as sibling elements updated via JS.
       Files: `templates/music/mix_list.html`, `templates/music/mix_detail.html`, `templates/music/track_list.html`, `templates/music/track_detail.html`

- [ ] 32. **Create `templates/videos/` templates**: `list.html`, `detail.html`. Video detail uses `<video controls>` with Cloudinary URL.
       Files: `templates/videos/list.html`, `templates/videos/detail.html`

- [ ] 33. **Create `templates/gallery/` templates**: `index.html` (CSS Grid, lightbox overlay), `detail.html`.
       Files: `templates/gallery/index.html`, `templates/gallery/detail.html`

- [ ] 34. **Create `templates/bookings/` templates**: `create.html`, `success.html` (tracking link with copy button), `tracking.html` (status timeline, quotation card, accept/decline buttons), `quotation_responded.html`.
       Files: `templates/bookings/create.html`, `templates/bookings/success.html`, `templates/bookings/tracking.html`, `templates/bookings/quotation_responded.html`

- [ ] 35. **Create `templates/chat/` templates**: `start.html`, `window.html` (message list, form, JS polling using `fetch` every 3s to `/chat/<pk>/poll/?since=<ts>`).
       Files: `templates/chat/start.html`, `templates/chat/window.html`

- [ ] 36. **Create `templates/dashboard/` templates**: `base_dashboard.html` (extends base.html, sidebar nav), `home.html` (stats cards), `bookings_list.html`, `booking_detail.html`, `messages_list.html`, `gallery_manage.html`, `music_manage.html`, `videos_manage.html`, `chat_list.html`, `chat_reply.html`, `site_settings.html`.
       Files: all dashboard templates

- [ ] 37. **Create `templates/registration/login.html`** (styled login page). Create `templates/errors/404.html` and `templates/errors/500.html` (on-brand error pages extending base.html without context processor dependencies — use static tag not site_settings).
       Files: `templates/registration/login.html`, `templates/errors/404.html`, `templates/errors/500.html`

- [ ] 38. **Create `static/css/main.css`** — full stylesheet: CSS custom properties (`--bg-primary: #0a0a0a`, `--bg-secondary: #111111`, `--bg-card: #1a1a1a`, `--accent: #c9a84c`, `--text-primary: #f5f5f5`, `--text-muted: #888`), reset, typography (Inter or system font), responsive nav, card grid, hero, audio player, gallery lightbox, booking form, status timeline, chat window, dashboard sidebar, button variants, mobile breakpoints at 768px and 480px.
       Files: `static/css/main.css`

- [ ] 39. **Create `static/js/main.js`** — vanilla JS modules: mobile nav toggle (`DOMContentLoaded`), audio player logic (attach to `<audio>`, update progress bar on `timeupdate`, seek on range `input` change, volume), gallery lightbox (click to open overlay, Escape to close, arrow keys to navigate), `startChatPolling(pk, initialSince)` exported on `window`, copy-to-clipboard for tracking link.
       Files: `static/js/main.js`

- [ ] 40. **Write chat and dashboard tests** in `apps/chat/tests.py` and `apps/dashboard/tests.py`. Chat: conversation creation, send message returns JSON, poll returns only new messages, wrong session gets 403. Dashboard: anonymous access redirects to login, staff user accesses dashboard home, booking status update creates history entry.
       Files: `apps/chat/tests.py`, `apps/dashboard/tests.py`
       Verify: `.venv\Scripts\python.exe manage.py test apps --verbosity=2`

---

## Phase 4 — Security Hardening, Deployment Prep, Final Polish (FEAT-004)

- [ ] 41. **Add security settings to `config/settings.py`** inside the `if os.environ.get("RENDER"):` block: `SECURE_HSTS_SECONDS = 31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`, `SECURE_HSTS_PRELOAD = True`, `SECURE_CONTENT_TYPE_NOSNIFF = True`, `X_FRAME_OPTIONS = 'DENY'`, `SECURE_REFERRER_POLICY = 'same-origin'`, `CSRF_TRUSTED_ORIGINS` parsed from env var.
       Files: `config/settings.py`

- [ ] 42. **Wire `handler404`/`handler500` in `config/urls.py`**: `handler404 = 'apps.core.views.handler404'`; `handler500 = 'apps.core.views.handler500'`.
       Files: `config/urls.py`

- [ ] 43. **Create `render.yaml`** in project root for Render deployment.
       Files: `render.yaml`

- [ ] 44. **Create `.env.example`** documenting all environment variables.
       Files: `.env.example`

- [ ] 45. **Create or update `.gitignore`** to include `.env`, `db.sqlite3`, `staticfiles/`, `media/`, `__pycache__/`, `*.pyc`, `.venv/`.
       Files: `.gitignore`

- [ ] 46. **Create/update `README.md`** with local setup steps, env var table, Cloudinary setup guide, Render deployment steps.
       Files: `README.md`

- [ ] 47. **Run full test suite and collectstatic** as final verification.
       Verify: `.venv\Scripts\python.exe manage.py test apps --verbosity=2` ; `.venv\Scripts\python.exe manage.py collectstatic --noinput`

---

## Settings Additions Summary

```python
# Add to config/settings.py

# Remove deprecated key:
# STATICFILES_STORAGE = "whitenoise.storage.StaticFilesStorage"  ← DELETE THIS LINE

STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# In TEMPLATES[0]['OPTIONS']['context_processors'], add:
# "apps.core.context_processors.site_settings"

# In INSTALLED_APPS, add after existing entries:
# "apps.core", "apps.music", "apps.videos", "apps.gallery",
# "apps.bookings", "apps.chat", "apps.dashboard"

# In if os.environ.get("RENDER"): block, add:
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
```

---

## URL Namespace Plan

| App       | prefix       | app_name    | Example named URL               |
|-----------|-------------|-------------|----------------------------------|
| core      | ``          | `core`      | `{% url 'core:home' %}`         |
| music     | `music/`    | `music`     | `{% url 'music:mix_detail' slug=mix.slug %}` |
| videos    | `videos/`   | `videos`    | `{% url 'videos:list' %}`       |
| gallery   | `gallery/`  | `gallery`   | `{% url 'gallery:index' %}`     |
| bookings  | `bookings/` | `bookings`  | `{% url 'bookings:create' %}`   |
| chat      | ``          | `chat`      | `{% url 'chat:start' %}`        |
| dashboard | `dashboard/`| `dashboard` | `{% url 'dashboard:home' %}`    |

---

## Template Inheritance

```
templates/base.html                      ← dark-themed HTML5 shell
  ├── templates/core/home.html
  ├── templates/core/about.html
  ├── templates/core/contact.html
  ├── templates/music/mix_list.html
  ├── templates/music/mix_detail.html
  ├── templates/videos/list.html
  ├── templates/gallery/index.html
  ├── templates/bookings/create.html
  ├── templates/bookings/tracking.html
  ├── templates/chat/start.html
  ├── templates/chat/window.html
  ├── templates/registration/login.html
  └── templates/dashboard/base_dashboard.html
        └── templates/dashboard/*.html    ← all dashboard pages
```

---

## Model Relationships

```
SiteSettings (singleton)
ContactMessage

Category ←── Mix
         ←── Track

VideoCategory ←── Video

GalleryCategory ←── GalleryImage

Booking ──→ Quotation (OneToOne)
        ──→ BookingStatusHistory[] (FK)
        ──→ BookingMessage[] (FK)
        ←── Conversation (FK nullable)

Conversation ──→ Message[]
```

---

## Migration Order

1. `core` (no FK deps)
2. `music` (no FK deps)
3. `videos` (no FK deps)
4. `gallery` (no FK deps)
5. `bookings` (FK to auth.User for `changed_by`)
6. `chat` (FK to bookings.Booking)
7. `dashboard` (no models — empty migration)

Run: `.venv\Scripts\python.exe manage.py makemigrations core music videos gallery bookings chat`

---

## Potential Gotchas

1. **`CloudinaryField` with `resource_type`**: `CloudinaryField('audio', resource_type='raw')` for audio files. Without this, Cloudinary treats them as images and rejects MP3/FLAC/WAV uploads.

2. **`STATICFILES_STORAGE` duplicate**: The existing `settings.py` has this deprecated key alongside the correct `STORAGES` dict. Django 5.2 will warn about it. Remove the deprecated key.

3. **`STATICFILES_DIRS` must not include `STATIC_ROOT`**: `STATIC_ROOT = BASE_DIR / 'staticfiles'` and `STATICFILES_DIRS = [BASE_DIR / 'static']` — these are different directories. ✓

4. **Windows paths in `STATICFILES_DIRS`**: Use `BASE_DIR / "static"` (pathlib) — already consistent with existing settings style.

5. **`Conversation.session_key`**: Call `request.session.save()` (or access `request.session.session_key` after modifying session data) to ensure the session exists and has a key before storing it. If the session doesn't exist, `session_key` may be `None`.

6. **`handler404`/`handler500` template context**: Django's error handlers do NOT run context processors. The error templates (`templates/errors/404.html`) must NOT rely on `{{ site_settings }}` from the context processor. Use `{% load static %}` directly instead.

7. **Booking token URL kwarg type**: Use `<str:token>` not `<slug:token>` in URL patterns — `token_urlsafe` output may contain `-` and `_` which are valid for `<str:>` but `<slug:>` also allows them. Either works, but `<str:>` is more explicit.

8. **UUID in URL**: The `Booking.reference` is a UUID but it's only used as a display reference, not in public URLs (which use the opaque `token`). The dashboard uses `<uuid:reference>` in URLs so staff can navigate bookings by reference.

9. **`channels` installed but not needed**: The existing `requirements.txt` includes `channels==4.3.2`. Do not configure it in settings (no `CHANNEL_LAYERS`, no ASGI routing). Polling-only chat works fine with WSGI.

10. **`cloudinary_storage` in `INSTALLED_APPS`**: Must remain FIRST in `INSTALLED_APPS` (before `django.contrib.staticfiles`) to override the default storage backend. Already correctly positioned in existing settings.

---

## Test Strategy

Each app has a `tests.py`. Use `django.test.TestCase` throughout. Tests use `self.client` for HTTP assertions. Cloudinary uploads are not tested (would require live credentials and network). Instead, mock `CloudinaryField` fields with `blank=True` where needed or use `SimpleUploadedFile` for image fields. Key test coverage:

- **core**: Home 200, about 200, contact form saves model, invalid email rejected
- **music**: Mix list 200, mix detail increments play_count, unpublished mix returns 404
- **videos**: Video list 200, unpublished video returns 404
- **gallery**: Gallery index 200
- **bookings**: Form creates Booking+token, past date rejected, track view 200/404, quotation respond rejects invalid status
- **chat**: Start creates Conversation, send returns JSON, poll returns delta, wrong session 403
- **dashboard**: Anonymous → redirect to login, staff user → 200, status update creates history entry

Run all: `.venv\Scripts\python.exe manage.py test apps --verbosity=2`
