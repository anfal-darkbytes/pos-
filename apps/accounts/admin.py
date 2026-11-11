from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.accounts.models import PasswordResetOTP, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "name", "role", "is_active", "is_staff", "date_joined"]
    list_filter = ["role", "is_active", "is_staff"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Pulse POS Info", {"fields": ("name", "role", "phone")}),
    )


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ["email", "otp", "otp_expires_at", "used", "created_at"]
    list_filter = ["used"]
    search_fields = ["email"]

