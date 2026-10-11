from urllib.parse import unquote, urlsplit


def cloudinary_configuration(environ):
    """Resolve explicit Cloudinary variables, falling back to CLOUDINARY_URL."""
    configuration = {
        "CLOUD_NAME": environ.get("CLOUDINARY_CLOUD_NAME", "").strip(),
        "API_KEY": environ.get("CLOUDINARY_API_KEY", "").strip(),
        "API_SECRET": environ.get("CLOUDINARY_API_SECRET", "").strip(),
    }
    cloudinary_url = environ.get("CLOUDINARY_URL", "").strip()
    if cloudinary_url:
        try:
            parsed_url = urlsplit(cloudinary_url)
            if parsed_url.scheme == "cloudinary" and parsed_url.hostname:
                configuration["CLOUD_NAME"] = (
                    configuration["CLOUD_NAME"] or parsed_url.hostname
                )
                configuration["API_KEY"] = (
                    configuration["API_KEY"] or unquote(parsed_url.username or "")
                )
                configuration["API_SECRET"] = (
                    configuration["API_SECRET"] or unquote(parsed_url.password or "")
                )
        except ValueError:
            pass
    return configuration


def missing_cloudinary_settings(configuration):
    setting_names = {
        "CLOUD_NAME": "CLOUDINARY_CLOUD_NAME",
        "API_KEY": "CLOUDINARY_API_KEY",
        "API_SECRET": "CLOUDINARY_API_SECRET",
    }
    return tuple(
        setting_names[key]
        for key, value in configuration.items()
        if key in setting_names and not value
    )
