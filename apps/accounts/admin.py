from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class ProtectedUserAdmin(UserAdmin):
    def has_delete_permission(self, request, obj=None):
        return False
