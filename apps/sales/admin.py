from django.contrib import admin
from apps.sales.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "name", "price", "cost", "quantity", "subtotal"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "customer", "cashier_name", "total", "payment_method", "payment_status", "status", "created_at"]
    list_filter = ["payment_method", "payment_status", "status"]
    search_fields = ["order_number", "customer__name", "cashier_name"]
    inlines = [OrderItemInline]

