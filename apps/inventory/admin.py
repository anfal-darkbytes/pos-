from django.contrib import admin
from apps.inventory.models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "color", "created_at"]
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "barcode", "category", "price", "cost", "stock", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name", "sku", "barcode"]

