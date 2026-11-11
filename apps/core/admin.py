from django.contrib import admin
from apps.core.models import StoreSettings


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ["store_name", "phone", "email", "tax_rate", "currency", "updated_at"]

