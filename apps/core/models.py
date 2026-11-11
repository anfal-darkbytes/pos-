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

    # SMTP Configuration
    smtp_host = models.CharField(max_length=150, blank=True, null=True)
    smtp_port = models.CharField(max_length=10, blank=True, null=True)
    smtp_user = models.CharField(max_length=150, blank=True, null=True)
    smtp_pass = models.CharField(max_length=150, blank=True, null=True)
    smtp_from_email = models.CharField(max_length=150, blank=True, null=True)

    # Google Drive Integration
    gdrive_client_id = models.TextField(blank=True, null=True)
    gdrive_client_secret = models.TextField(blank=True, null=True)

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
            "smtp_host": self.smtp_host or "",
            "smtp_port": self.smtp_port or "",
            "smtp_user": self.smtp_user or "",
            "smtp_pass": self.smtp_pass or "",
            "smtp_from_email": self.smtp_from_email or "",
            "gdrive_client_id": self.gdrive_client_id or "",
            "gdrive_client_secret": self.gdrive_client_secret or "",
        }

