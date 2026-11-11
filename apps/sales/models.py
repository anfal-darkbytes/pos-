import uuid
from django.db import models
from apps.customers.models import Customer
from apps.inventory.models import Product


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    cashier_name = models.CharField(max_length=100, default="Cashier")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="cash")
    payment_status = models.CharField(max_length=50, default="paid")
    status = models.CharField(max_length=50, default="completed")
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "orders"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["customer"]),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.total})"

    @property
    def customer_name(self):
        return self.customer.name if self.customer else "Walk-in Customer"

    def to_dict(self):
        return {
            "id": str(self.id),
            "order_number": self.order_number,
            "customer_id": str(self.customer_id) if self.customer_id else None,
            "customer_name": self.customer_name,
            "cashier_name": self.cashier_name,
            "subtotal": float(self.subtotal),
            "tax_rate": float(self.tax_rate),
            "tax": float(self.tax),
            "discount": float(self.discount),
            "total": float(self.total),
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "status": self.status,
            "note": self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "items": [it.to_dict() for it in self.items.all()],
        }


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, related_name="order_items")
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.IntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "order_items"
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"{self.name} x {self.quantity}"

    def to_dict(self):
        return {
            "id": str(self.id),
            "order_id": str(self.order_id),
            "product_id": str(self.product_id),
            "name": self.name,
            "price": float(self.price),
            "cost": float(self.cost),
            "quantity": self.quantity,
            "subtotal": float(self.subtotal),
            "category_name": self.product.category.name if self.product and self.product.category else "",
            "category_id": str(self.product.category_id) if self.product else "",
        }

