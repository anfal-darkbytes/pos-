from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.core.models import StoreSettings
from apps.customers.models import Customer
from apps.inventory.models import Category


class Command(BaseCommand):
    help = "Initialize Pulse POS with default store settings, admin account, and base categories (no dummy data)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing Pulse POS..."))

        # 1. Store Settings
        settings, created = StoreSettings.objects.get_or_create(
            defaults={
                "store_name": "Pulse POS Store",
                "address": "123 Main Street",
                "phone": "+1 555 0100",
                "email": "store@pulsepos.com",
                "tax_rate": 8.00,
                "currency": "USD",
                "currency_symbol": "$",
                "receipt_footer": "Thank you for shopping with us!",
                "low_stock_alert_enabled": True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS("✓ Default Store Settings created."))
        else:
            settings.store_name = "Pulse POS Store"
            settings.email = "store@pulsepos.com"
            settings.save()
            self.stdout.write("✓ Store Settings updated to Pulse POS.")

        # 2. Administrator account
        admin_email = "admin@pulsepos.com"
        admin_user = User.objects.filter(email__in=[admin_email, "admin@quickpos.com"]).first()
        if not admin_user:
            admin_user = User.objects.create(
                username="admin",
                name="Administrator",
                email=admin_email,
                role="admin",
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            admin_user.set_password("Admin@202600")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Admin user created: {admin_email} (Password: Admin@202600)"))
        else:
            admin_user.email = admin_email
            admin_user.save()
            self.stdout.write(f"✓ Admin user updated to {admin_email}.")

        # 3. Default Walk-in Customer
        walk_in, c_created = Customer.objects.get_or_create(
            name="Walk-in Customer",
            defaults={
                "loyalty_points": 0,
                "total_spent": 0.00,
                "orders_count": 0,
                "note": "Default system customer for anonymous walk-in sales",
            }
        )
        if c_created:
            self.stdout.write(self.style.SUCCESS("✓ Walk-in customer registered."))

        # 4. Standard clean categories (catalog taxonomy)
        base_categories = [
            {"name": "Beverages", "description": "Hot and cold drinks", "color": "#f97316"},
            {"name": "Bakery", "description": "Bread, pastries, and baked goods", "color": "#eab308"},
            {"name": "Snacks", "description": "Chips, candy, nuts, and snacks", "color": "#22c55e"},
            {"name": "Dairy", "description": "Milk, cheese, yogurt, and eggs", "color": "#06b6d4"},
            {"name": "Produce", "description": "Fresh fruits and vegetables", "color": "#84cc16"},
            {"name": "Household", "description": "Cleaning and home supplies", "color": "#a855f7"},
        ]
        created_cats = 0
        for cat in base_categories:
            _, created = Category.objects.get_or_create(
                name=cat["name"],
                defaults={"description": cat["description"], "color": cat["color"]}
            )
            if created:
                created_cats += 1

        if created_cats > 0:
            self.stdout.write(self.style.SUCCESS(f"✓ Initialized {created_cats} base catalog categories."))

        self.stdout.write(self.style.SUCCESS("\n🎉 Pulse POS initialization complete!"))

