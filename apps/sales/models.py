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
    client_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    is_offline_sync = models.BooleanField(default=False)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "orders"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["client_id"]),
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
            "client_id": self.client_id,
            "is_offline_sync": self.is_offline_sync,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "items": [it.to_dict() for it in self.items.all()],
            "payments": [p.to_dict() for p in self.payments.all()],
        }


class OrderPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.CharField(max_length=30)  # "cash", "bank", "wallet"
    account = models.ForeignKey("core.PaymentAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_payments")
    account_name = models.CharField(max_length=100, blank=True, null=True)  # e.g. "Meezan Bank", "JazzCash"
    account_title = models.CharField(max_length=150, blank=True, null=True)
    account_number = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tendered = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    change = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_payments"
        verbose_name = "Order Payment"
        verbose_name_plural = "Order Payments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["payment_method"]),
        ]

    def __str__(self):
        return f"{self.payment_method.capitalize()}: {self.amount} ({self.account_name or 'Default'})"

    def to_dict(self):
        return {
            "id": str(self.id),
            "payment_method": self.payment_method,
            "account_id": str(self.account_id) if self.account_id else None,
            "account_name": self.account_name or "",
            "account_title": self.account_title or "",
            "account_number": self.account_number or "",
            "amount": float(self.amount),
            "tendered": float(self.tendered),
            "change": float(self.change),
            "reference": self.reference or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
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

