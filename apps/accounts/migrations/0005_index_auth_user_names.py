from django.conf import settings
from django.db import migrations


INDEX_FIELDS = {
    "accounts_auth_first_idx": "first_name",
    "accounts_auth_last_idx": "last_name",
}


def update_name_indexes(apps, schema_editor, *, create):
    user_app, user_model_name = settings.AUTH_USER_MODEL.split(".")
    user_model = apps.get_model(user_app, user_model_name)
    quote = schema_editor.connection.ops.quote_name
    table = quote(user_model._meta.db_table)
    concurrent = (
        " CONCURRENTLY"
        if schema_editor.connection.vendor == "postgresql"
        else ""
    )
    for index_name, field_name in INDEX_FIELDS.items():
        index = quote(index_name)
        if create:
            column = quote(user_model._meta.get_field(field_name).column)
            schema_editor.execute(
                f"CREATE INDEX{concurrent} IF NOT EXISTS {index} "
                f"ON {table} ({column})"
            )
        else:
            schema_editor.execute(
                f"DROP INDEX{concurrent} IF EXISTS {index}"
            )


def create_name_indexes(apps, schema_editor):
    update_name_indexes(apps, schema_editor, create=True)


def drop_name_indexes(apps, schema_editor):
    update_name_indexes(apps, schema_editor, create=False)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0004_alter_ratelimitbucket_action"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_name_indexes, drop_name_indexes),
    ]
