from django.contrib import admin
from apps.customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone", "loyalty_points", "total_spent", "orders_count", "tier", "created_at"]
    search_fields = ["name", "email", "phone"]

