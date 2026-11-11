import uuid
from django.db import models


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=30, default="#10b981")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description or "",
            "color": self.color,
        }


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    barcode = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.RESTRICT, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    unit = models.CharField(max_length=20, default="pcs")
    image_url = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def category_id_str(self):
        return str(self.category_id)

    @property
    def category_name(self):
        return self.category.name if self.category else ""

    @property
    def category_color(self):
        return self.category.color if self.category else "#10b981"

    @property
    def margin(self):
        if self.price and float(self.price) > 0:
            return float((self.price - self.cost) / self.price * 100)
        return 0.0

    @property
    def is_low(self):
        return self.stock <= self.low_stock_threshold

    @property
    def stock_value(self):
        return float(self.cost * self.stock)

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "sku": self.sku,
            "barcode": self.barcode or "",
            "description": self.description or "",
            "category_id": str(self.category_id),
            "category_name": self.category_name,
            "category_color": self.category_color,
            "price": float(self.price),
            "cost": float(self.cost),
            "stock": self.stock,
            "low_stock_threshold": self.low_stock_threshold,
            "unit": self.unit,
            "image_url": self.image_url or "",
            "is_active": 1 if self.is_active else 0,
            "margin": self.margin,
            "is_low": self.is_low,
            "stock_value": self.stock_value,
        }

