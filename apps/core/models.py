import uuid
from django.db import models


class StoreSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_name = models.CharField(max_length=150, default="Pulse POS Store")
    address = models.TextField(default="123 Main Street")
    phone = models.CharField(max_length=50, default="+1 555 0100")
    email = models.EmailField(default="store@pulsepos.com")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=8.00)
    currency = models.CharField(max_length=10, default="USD")
    currency_symbol = models.CharField(max_length=10, default="$")
    receipt_footer = models.TextField(default="Thank you for shopping with us!")
    low_stock_alert_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settings"
        verbose_name = "Store Settings"
        verbose_name_plural = "Store Settings"

    def __str__(self):
        return self.store_name

    @classmethod
    def get_settings(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(store_name="Pulse POS Store")
        return obj

    def to_dict(self):
        return {
            "id": str(self.id),
            "store_name": self.store_name,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "tax_rate": float(self.tax_rate),
            "currency": self.currency,
            "currency_symbol": self.currency_symbol,
            "receipt_footer": self.receipt_footer,
            "low_stock_alert_enabled": self.low_stock_alert_enabled,
        }


class PaymentAccount(models.Model):
    CATEGORY_CHOICES = [
        ("bank", "Bank Account"),
        ("wallet", "Mobile Wallet"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="bank", db_index=True)
    name = models.CharField(max_length=100)  # e.g., Meezan Bank, Allied Bank, HBL, Easypaisa, JazzCash
    account_name = models.CharField(max_length=150)  # Account title / holder name
    account_number = models.CharField(max_length=100)  # Account number / IBAN / mobile number
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_accounts"
        verbose_name = "Payment Account"
        verbose_name_plural = "Payment Accounts"
        ordering = ["category", "name"]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name} - {self.account_name} ({self.account_number})"

    def to_dict(self):
        return {
            "id": str(self.id),
            "category": self.category,
            "category_label": self.get_category_display(),
            "name": self.name,
            "account_name": self.account_name,
            "account_number": self.account_number,
            "is_active": self.is_active,
            "is_default": self.is_default,
        }

    @classmethod
    def seed_default_accounts_if_empty(cls):
        if not cls.objects.exists():
            defaults = [
                {
                    "category": "bank",
                    "name": "Meezan Bank",
                    "account_name": "Pulse Retail Store",
                    "account_number": "01020304050607",
                    "is_default": True,
                },
                {
                    "category": "bank",
                    "name": "Allied Bank",
                    "account_name": "Pulse Retail Store",
                    "account_number": "02030405060708",
                    "is_default": False,
                },
                {
                    "category": "bank",
                    "name": "HBL Bank",
                    "account_name": "Pulse Retail Store",
                    "account_number": "03040506070809",
                    "is_default": False,
                },
                {
                    "category": "wallet",
                    "name": "Easypaisa",
                    "account_name": "Pulse POS Store",
                    "account_number": "03001234567",
                    "is_default": True,
                },
                {
                    "category": "wallet",
                    "name": "JazzCash",
                    "account_name": "Pulse POS Store",
                    "account_number": "03019876543",
                    "is_default": False,
                },
            ]
            for item in defaults:
                cls.objects.create(**item)


