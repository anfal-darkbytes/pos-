import uuid
from django.db import models


def calculate_tier(points):
    if points >= 400:
        return "Platinum", "bg-purple-500"
    if points >= 200:
        return "Gold", "bg-amber-500"
    if points >= 100:
        return "Silver", "bg-slate-400"
    return "Bronze", "bg-orange-700"


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    loyalty_points = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    orders_count = models.IntegerField(default=0)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customers"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.name

    @property
    def tier(self):
        return calculate_tier(self.loyalty_points)[0]

    @property
    def tier_color(self):
        return calculate_tier(self.loyalty_points)[1]

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "email": self.email or "",
            "phone": self.phone or "",
            "address": self.address or "",
            "loyalty_points": self.loyalty_points,
            "total_spent": float(self.total_spent),
            "orders_count": self.orders_count,
            "note": self.note or "",
            "tier": self.tier,
            "tier_color": self.tier_color,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }

