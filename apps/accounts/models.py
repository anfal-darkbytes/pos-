import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("cashier", "Cashier"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="cashier")
    phone = models.CharField(max_length=50, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.name or self.username or self.email

    @property
    def display_name(self):
        return self.name or self.username or self.email

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name or self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.date_joined.isoformat() if self.date_joined else "",
        }


class PasswordResetOTP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    otp = models.CharField(max_length=10)
    otp_expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_resets"
        indexes = [
            models.Index(fields=["email", "otp", "used"]),
        ]

    def __str__(self):
        return f"{self.email} - OTP {self.otp}"

