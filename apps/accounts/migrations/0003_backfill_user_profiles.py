from django.conf import settings
from django.db import migrations


def create_existing_profiles(apps, schema_editor):
    profile_model = apps.get_model("accounts", "UserProfile")
    user_app, user_model_name = settings.AUTH_USER_MODEL.split(".")
    user_model = apps.get_model(user_app, user_model_name)
    database = schema_editor.connection.alias
    batch = []
    for user in (
        user_model.objects.using(database)
        .only("pk", "date_joined")
        .iterator(chunk_size=1000)
    ):
        batch.append(
            profile_model(
                user_id=user.pk,
                phone_number="",
                location="",
                registered_at=user.date_joined,
            )
        )
        if len(batch) == 1000:
            profile_model.objects.using(database).bulk_create(
                batch,
                batch_size=1000,
                ignore_conflicts=True,
            )
            batch.clear()
    if batch:
        profile_model.objects.using(database).bulk_create(
            batch,
            batch_size=1000,
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0002_alter_userprofile_location_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            create_existing_profiles,
            reverse_code=migrations.RunPython.noop,
        )
    ]
