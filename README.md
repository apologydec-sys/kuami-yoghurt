# DJ Kuami Yoghurt

Django portfolio, music library, gallery, booking workflow, customer chat, and custom Super Admin portal.

## Local development

```powershell
cd C:\Users\Akanni-kweku\DJKuamiYoghurt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:DJANGO_SETTINGS_MODULE='config.settings'
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The custom portal is at `/portal/login/`. Local development uses `db.sqlite3` unless `DATABASE_URL` is set. Copy `.env.example` to `.env` and add real Cloudinary credentials, or set environment variables in PowerShell. Settings load `.env` before configuring Cloudinary; environment variables already supplied by the process take precedence. Never replace a working `.env` with example placeholders.

## Environment variables

| Variable | Required in production | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes | Long, private Django signing key |
| `DJANGO_DEBUG` | Yes | Set to `False`; `RENDER=true` also forces it off |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated hostnames; use the service/custom domain |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | For custom domains | Comma-separated full origins including `https://`; Render hostname is detected automatically |
| `DATABASE_URL` | Yes | Persistent PostgreSQL connection URL |
| `CLOUDINARY_CLOUD_NAME` | Yes | Cloudinary account name |
| `CLOUDINARY_API_KEY` | Yes | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Yes | Cloudinary API secret; server-side only |
| `RENDER` | Render | Set to `true` to enable Render production behavior |

Never put actual credentials in GitHub, source code, logs, `.env.example`, or client-side JavaScript. Generate a unique production secret and enter it only in the hosting provider's secret environment configuration.

## PostgreSQL and migrations

Production must use PostgreSQL via `DATABASE_URL`; SQLite is retained for local development. Create or select a persistent PostgreSQL service with a supported provider, then set its private/internal connection URL as `DATABASE_URL` on the web service. Provider availability, storage, backups, and pricing vary; check the provider's current terms and costs. A free database tier may expire, sleep, or have limited storage and is not a persistence guarantee.

Existing migrations are preserved. For an existing SQLite installation, applying the same migrations to a new PostgreSQL database creates its schema but does **not** copy existing SQLite records. Bookings, users, messages, and site settings require a planned data export/import if they must be retained. Do not point this app at production and migrate until the database is backed up and the change is approved.

Safe deployment sequence:

1. Review migration changes with `python manage.py makemigrations --check --dry-run` and `python manage.py showmigrations`.
2. Back up the current production database and confirm the target PostgreSQL URL.
3. Apply reviewed migrations explicitly from a Render one-off shell or approved release operation: `python manage.py migrate`.
4. Verify `python manage.py showmigrations` and test portal, bookings, and customer messaging.

The Render build does not run migrations automatically, to avoid unreviewed schema changes during every deploy.

## Cloudinary media

Set either `CLOUDINARY_URL` or all three of `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` in local/private hosting environment configuration. The application reports missing Cloudinary settings without printing their values. Artwork and images use the configured Cloudinary storage. Music `CloudinaryField`s currently specify `resource_type="raw"`; video uploads use `resource_type="video"`. These existing types are intentionally preserved for compatibility with stored media. Account upload-size and delivery restrictions depend on the Cloudinary plan.

Manual MP3 verification: upload a small licensed MP3 through the portal, confirm it saves and produces a Cloudinary URL, open that URL in a private browser session, inspect the response status/content type, then play and seek it on the public track or mix page. This has not been verified against a live Cloudinary account unless performed separately with real credentials and a real file.

## GitHub and Render

1. Review `git status` and ensure no `.env`, database, media uploads, or credentials are staged.
2. Push the existing project to a private or public GitHub repository as appropriate.
3. Create a Render Web Service from the repository and configure the persistent PostgreSQL provider separately. No paid resource is created by this repository configuration.
4. Set the environment variables above in Render. The blueprint includes `DATABASE_URL` and Cloudinary credentials as `sync: false`; populate these in the Render dashboard. Set `DJANGO_ALLOWED_HOSTS` to `.onrender.com` or explicit hostnames and set `DJANGO_CSRF_TRUSTED_ORIGINS` for custom domains.
5. Build and deploy, then run the reviewed migration command from a Render shell after backup/approval.
6. Create the authorized portal account from the Render shell with `python manage.py createsuperuser`; do not use a default account/password.
7. Verify the public homepage, `/portal/login/`, a booking submission/tracking link, static assets, Cloudinary uploads, and database persistence across a restart.

Render commands:

- Build: `python -m pip install --upgrade pip && pip install -r requirements.txt && python manage.py collectstatic --noinput --upload-unhashed-files`
- Start: `gunicorn config.wsgi:application --workers 2 --bind 0.0.0.0:$PORT`
- Migration (manual, after review/backup): `python manage.py migrate`

## Troubleshooting

- `ImproperlyConfigured: ... must be set`: configure required production environment variables; do not enable debug to bypass validation.
- `DisallowedHost`: add the exact service/custom hostname to `DJANGO_ALLOWED_HOSTS`.
- CSRF origin failure: add the full `https://` origin to `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Database connection failure: verify the private URL, network access, credentials, provider status, and SSL support. Production connections require SSL.
- Static file errors: rerun `python manage.py collectstatic --noinput --upload-unhashed-files` and inspect the Render build output. The Cloudinary storage package overrides this command and needs the flag when WhiteNoise serves unhashed static filenames.
- Cloudinary upload failure: verify credentials, account upload limits, file format, and storage response; do not treat a saved model URL alone as proof of playback.
