import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.core.models import StoreSettings
from apps.customers.models import Customer
from apps.inventory.models import Category, Product
from apps.sales.models import Order, OrderItem


def generate_grocery_svgs(output_dir):
    """
    Generates clean, modern, vector SVG graphics for all grocery products.
    Each SVG features a soft gradient squircle card with crisp food iconography.
    """
    os.makedirs(output_dir, exist_ok=True)

    items = {
        "avocados": ("#10b981", "#059669", "🥑", "Avocados"),
        "apples": ("#ef4444", "#dc2626", "🍎", "Apples"),
        "bananas": ("#f59e0b", "#d97706", "🍌", "Bananas"),
        "spinach": ("#10b981", "#047857", "🥬", "Spinach"),
        "tomatoes": ("#ef4444", "#b91c1c", "🍅", "Tomatoes"),
        "cucumber": ("#10b981", "#059669", "🥒", "Cucumber"),
        "milk": ("#3b82f6", "#2563eb", "🥛", "Milk"),
        "eggs": ("#f59e0b", "#d97706", "🥚", "Eggs"),
        "yogurt": ("#3b82f6", "#1d4ed8", "🥣", "Yogurt"),
        "cheese": ("#f59e0b", "#b45309", "🧀", "Cheese"),
        "butter": ("#f59e0b", "#d97706", "🧈", "Butter"),
        "almond_milk": ("#8b5cf6", "#6d28d9", "🌰", "Almond Milk"),
        "sourdough": ("#f59e0b", "#b45309", "🍞", "Sourdough"),
        "croissants": ("#f59e0b", "#d97706", "🥐", "Croissants"),
        "wheat_bread": ("#d97706", "#92400e", "🍞", "Whole Wheat"),
        "burger_buns": ("#f59e0b", "#b45309", "🍔", "Brioche Buns"),
        "cookies": ("#d97706", "#78350f", "🍪", "Cookies"),
        "salmon": ("#f43f5e", "#be123c", "🐟", "Salmon"),
        "chicken": ("#f97316", "#c2410c", "🍗", "Chicken"),
        "ground_beef": ("#b91c1c", "#7f1d1d", "🥩", "Ground Beef"),
        "bacon": ("#dc2626", "#991b1b", "🥓", "Smoked Bacon"),
        "orange_juice": ("#f97316", "#ea580c", "🍊", "Orange Juice"),
        "coffee": ("#78350f", "#451a03", "☕", "Coffee Beans"),
        "sparkling_water": ("#06b6d4", "#0891b2", "🥤", "Sparkling Water"),
        "green_tea": ("#10b981", "#047857", "🍵", "Green Tea"),
        "kombucha": ("#8b5cf6", "#6d28d9", "🧃", "Kombucha"),
        "olive_oil": ("#84cc16", "#4d7c0f", "🫒", "Olive Oil"),
        "pasta": ("#eab308", "#ca8a04", "🍝", "Pasta"),
        "salt": ("#ec4899", "#db2777", "🧂", "Himalayan Salt"),
        "oats": ("#d97706", "#b45309", "🌾", "Rolled Oats"),
        "rice": ("#64748b", "#475569", "🍚", "Basmati Rice"),
        "honey": ("#f59e0b", "#d97706", "🍯", "Raw Honey"),
        "chips": ("#f59e0b", "#b45309", "🥔", "Potato Chips"),
        "pistachios": ("#84cc16", "#65a30d", "🥜", "Pistachios"),
        "chocolate": ("#78350f", "#451a03", "🍫", "Dark Chocolate"),
        "dates": ("#92400e", "#713f12", "🌴", "Medjool Dates"),
        "crackers": ("#f59e0b", "#d97706", "🍘", "Seed Crackers"),
    }

    for slug, (c1, c2, emoji, title) in items.items():
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
  <defs>
    <linearGradient id="bg_{slug}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}" stop-opacity="0.16" />
      <stop offset="100%" stop-color="{c2}" stop-opacity="0.08" />
    </linearGradient>
    <linearGradient id="badge_{slug}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}" />
      <stop offset="100%" stop-color="{c2}" />
    </linearGradient>
    <filter id="shadow_{slug}" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="{c1}" flood-opacity="0.25" />
    </filter>
  </defs>
  <rect width="200" height="200" rx="24" fill="url(#bg_{slug})" />
  <rect x="1" y="1" width="198" height="198" rx="23" fill="none" stroke="{c1}" stroke-opacity="0.25" stroke-width="1.5" />
  
  <!-- Central Icon Plate -->
  <circle cx="100" cy="85" r="48" fill="white" filter="url(#shadow_{slug})" opacity="0.95" />
  <circle cx="100" cy="85" r="48" fill="url(#badge_{slug})" opacity="0.12" />
  <text x="100" y="103" font-size="44" text-anchor="middle" font-family="'Segoe UI Emoji', 'Apple Color Emoji', sans-serif">{emoji}</text>
  
  <!-- Product Label -->
  <text x="100" y="158" font-size="13" font-weight="700" fill="#1f2937" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif">{title}</text>
  <text x="100" y="174" font-size="9.5" font-weight="600" fill="{c1}" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif" letter-spacing="0.5">PREMIUM GROCERY</text>
</svg>"""
        file_path = os.path.join(output_dir, f"{slug}.svg")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)


class Command(BaseCommand):
    help = "Seed comprehensive realistic grocery data with prices, margins, images, and live real-time production scenario."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🌱 Starting Grocery Data & Production Scenario Seeding..."))

        # 1. Generate Product Vector Images
        output_dir = os.path.join("static", "images", "products")
        generate_grocery_svgs(output_dir)
        self.stdout.write(self.style.SUCCESS("✓ Generated 37 vector product images in static/images/products/"))

        with transaction.atomic():
            # 2. Configure Store Settings for Grocery Supermarket
            settings = StoreSettings.get_settings()
            settings.store_name = "Pulse Fresh Supermarket"
            settings.address = "742 Evergreen Boulevard, Suite 100"
            settings.phone = "+1 (555) 382-7000"
            settings.email = "support@pulsefresh.com"
            settings.tax_rate = Decimal("7.50")
            settings.currency = "USD"
            settings.currency_symbol = "$"
            settings.receipt_footer = "Fresh Produce · Quality Groceries · Thank You for Shopping Local!"
            settings.low_stock_alert_enabled = True
            settings.save()
            self.stdout.write(self.style.SUCCESS("✓ Updated Store Settings to 'Pulse Fresh Supermarket' (7.5% Tax Rate)"))

            # 3. Ensure Staff Accounts
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.create(
                    username="admin",
                    name="Store Manager",
                    email="admin@pulsepos.com",
                    role="admin",
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                )
                admin_user.set_password("Admin@202600")
                admin_user.save()

            cashier_user, _ = User.objects.get_or_create(
                username="sarah",
                defaults={
                    "name": "Sarah Adams",
                    "email": "sarah@pulsepos.com",
                    "role": "cashier",
                    "is_active": True,
                },
            )
            if _:
                cashier_user.set_password("Cashier@202600")
                cashier_user.save()

            # 4. Grocery Categories
            categories_def = [
                ("Fresh Produce", "Farm-fresh organic fruits, vegetables, and leafy greens", "#10b981"),
                ("Dairy & Eggs", "Farm milk, artisanal cheeses, butter, and free-range eggs", "#3b82f6"),
                ("Bakery & Bread", "Freshly baked artisan sourdough, brioche, and pastries", "#f59e0b"),
                ("Meat & Seafood", "Wild caught fish, organic chicken, and grass-fed beef", "#ef4444"),
                ("Beverages & Drinks", "Cold-pressed juices, specialty coffee, and mineral water", "#8b5cf6"),
                ("Pantry & Grains", "Extra virgin oils, organic pasta, ancient grains, and spices", "#d97706"),
                ("Snacks & Confectionery", "Kettle chips, nuts, gourmet dark chocolates, and crackers", "#ec4899"),
            ]

            cat_map = {}
            for name, desc, color in categories_def:
                cat, _ = Category.objects.update_or_create(
                    name=name,
                    defaults={"description": desc, "color": color},
                )
                cat_map[name] = cat
            self.stdout.write(self.style.SUCCESS(f"✓ Initialized {len(cat_map)} Grocery Departments"))

            # 5. Grocery Products
            products_def = [
                # Produce
                ("Fresh Produce", "Organic Hass Avocados (4-Pack)", "GROC-PRD-001", "071234560001", 4.99, 2.40, 45, 10, "pack", "/static/images/products/avocados.svg"),
                ("Fresh Produce", "Honeycrisp Apples (1kg)", "GROC-PRD-002", "071234560002", 3.99, 1.85, 60, 15, "kg", "/static/images/products/apples.svg"),
                ("Fresh Produce", "Organic Cavendish Bananas (Bunch)", "GROC-PRD-003", "071234560003", 1.89, 0.75, 85, 20, "bunch", "/static/images/products/bananas.svg"),
                ("Fresh Produce", "Baby Spinach Leaves (300g)", "GROC-PRD-004", "071234560004", 2.99, 1.20, 35, 8, "box", "/static/images/products/spinach.svg"),
                ("Fresh Produce", "Vine-Ripened Roma Tomatoes (1kg)", "GROC-PRD-005", "071234560005", 3.49, 1.50, 40, 10, "kg", "/static/images/products/tomatoes.svg"),
                ("Fresh Produce", "English Cucumbers", "GROC-PRD-006", "071234560006", 1.49, 0.60, 50, 12, "pcs", "/static/images/products/cucumber.svg"),
                
                # Dairy
                ("Dairy & Eggs", "Whole Grade A Milk (1 Gallon)", "GROC-DAI-001", "071234560007", 4.29, 2.30, 38, 10, "jug", "/static/images/products/milk.svg"),
                ("Dairy & Eggs", "Farm Fresh Large Brown Eggs (12ct)", "GROC-DAI-002", "071234560008", 3.89, 1.90, 55, 12, "carton", "/static/images/products/eggs.svg"),
                ("Dairy & Eggs", "Greek Plain Whole Milk Yogurt (32oz)", "GROC-DAI-003", "071234560009", 5.49, 2.80, 28, 8, "tub", "/static/images/products/yogurt.svg"),
                ("Dairy & Eggs", "Aged Sharp Cheddar Cheese (250g)", "GROC-DAI-004", "071234560010", 4.79, 2.40, 30, 10, "block", "/static/images/products/cheese.svg"),
                ("Dairy & Eggs", "European Style Unsalted Butter (454g)", "GROC-DAI-005", "071234560011", 5.29, 2.75, 42, 10, "pack", "/static/images/products/butter.svg"),
                ("Dairy & Eggs", "Barista Blend Almond Milk (1L)", "GROC-DAI-006", "071234560012", 3.79, 1.95, 24, 8, "carton", "/static/images/products/almond_milk.svg"),
                
                # Bakery
                ("Bakery & Bread", "Artisan Sourdough Boule (750g)", "GROC-BAK-001", "071234560013", 5.99, 2.20, 4, 6, "loaf", "/static/images/products/sourdough.svg"), # Low stock scenario
                ("Bakery & Bread", "Fresh All-Butter Croissants (4-Pack)", "GROC-BAK-002", "071234560014", 4.49, 1.70, 22, 6, "pack", "/static/images/products/croissants.svg"),
                ("Bakery & Bread", "100% Whole Wheat Sliced Loaf (680g)", "GROC-BAK-003", "071234560015", 3.29, 1.30, 34, 8, "loaf", "/static/images/products/wheat_bread.svg"),
                ("Bakery & Bread", "Brioche Gourmet Burger Buns (6-Pack)", "GROC-BAK-004", "071234560016", 3.99, 1.60, 25, 6, "pack", "/static/images/products/burger_buns.svg"),
                ("Bakery & Bread", "Chocolate Chip Bakery Cookies (8-Pack)", "GROC-BAK-005", "071234560017", 4.99, 1.90, 0, 5, "box", "/static/images/products/cookies.svg"), # Out of stock scenario
                
                # Meat
                ("Meat & Seafood", "Wild Caught Atlantic Salmon Fillets (500g)", "GROC-MEA-001", "071234560018", 12.99, 7.50, 3, 6, "pack", "/static/images/products/salmon.svg"), # Low stock scenario
                ("Meat & Seafood", "Organic Boneless Chicken Breasts (1kg)", "GROC-MEA-002", "071234560019", 9.49, 5.20, 25, 8, "tray", "/static/images/products/chicken.svg"),
                ("Meat & Seafood", "Grass-Fed Ground Beef 85/15 (500g)", "GROC-MEA-003", "071234560020", 6.99, 3.80, 30, 8, "pack", "/static/images/products/ground_beef.svg"),
                ("Meat & Seafood", "Thick Cut Hickory Smoked Bacon (375g)", "GROC-MEA-004", "071234560021", 5.89, 3.10, 26, 8, "pack", "/static/images/products/bacon.svg"),
                
                # Beverages
                ("Beverages & Drinks", "Cold-Pressed 100% Orange Juice (1.75L)", "GROC-BEV-001", "071234560022", 4.99, 2.60, 32, 10, "bottle", "/static/images/products/orange_juice.svg"),
                ("Beverages & Drinks", "Organic Whole Bean Espresso Coffee (454g)", "GROC-BEV-002", "071234560023", 11.49, 6.20, 22, 6, "bag", "/static/images/products/coffee.svg"),
                ("Beverages & Drinks", "Italian Sparkling Mineral Water (12-Pack)", "GROC-BEV-003", "071234560024", 6.49, 3.20, 40, 10, "case", "/static/images/products/sparkling_water.svg"),
                ("Beverages & Drinks", "Japanese Organic Sencha Green Tea (20 bags)", "GROC-BEV-004", "071234560025", 4.29, 1.90, 28, 8, "box", "/static/images/products/green_tea.svg"),
                ("Beverages & Drinks", "Organic Ginger Lemon Kombucha (480ml)", "GROC-BEV-005", "071234560026", 3.69, 1.80, 30, 8, "bottle", "/static/images/products/kombucha.svg"),
                
                # Pantry
                ("Pantry & Grains", "Cold-Extracted Extra Virgin Olive Oil (750ml)", "GROC-PAN-001", "071234560027", 10.99, 6.10, 26, 8, "bottle", "/static/images/products/olive_oil.svg"),
                ("Pantry & Grains", "Bronze-Cut Penne Rigate Pasta (500g)", "GROC-PAN-002", "071234560028", 2.49, 0.95, 65, 15, "box", "/static/images/products/pasta.svg"),
                ("Pantry & Grains", "Himalayan Pink Rock Salt Grinder (200g)", "GROC-PAN-003", "071234560029", 3.99, 1.60, 35, 10, "grinder", "/static/images/products/salt.svg"),
                ("Pantry & Grains", "Organic Rolled Whole Oats (1kg)", "GROC-PAN-004", "071234560030", 4.49, 2.10, 40, 10, "pouch", "/static/images/products/oats.svg"),
                ("Pantry & Grains", "Royal Aged Long Grain Basmati Rice (2kg)", "GROC-PAN-005", "071234560031", 7.99, 4.20, 30, 8, "bag", "/static/images/products/rice.svg"),
                ("Pantry & Grains", "Wildflower Raw Unfiltered Honey (500g)", "GROC-PAN-006", "071234560032", 7.49, 3.90, 24, 6, "jar", "/static/images/products/honey.svg"),
                
                # Snacks
                ("Snacks & Confectionery", "Sea Salt Kettle Cooked Potato Chips (200g)", "GROC-SNK-001", "071234560033", 3.49, 1.40, 45, 12, "bag", "/static/images/products/chips.svg"),
                ("Snacks & Confectionery", "Roasted & Salted California Pistachios (300g)", "GROC-SNK-002", "071234560034", 6.99, 3.80, 28, 8, "pouch", "/static/images/products/pistachios.svg"),
                ("Snacks & Confectionery", "Swiss 72% Rich Dark Chocolate (100g)", "GROC-SNK-003", "071234560035", 3.29, 1.50, 50, 15, "bar", "/static/images/products/chocolate.svg"),
                ("Snacks & Confectionery", "Organic Medjool Dates (400g Box)", "GROC-SNK-004", "071234560036", 5.99, 3.00, 5, 6, "box", "/static/images/products/dates.svg"), # Low stock scenario
                ("Snacks & Confectionery", "Gluten-Free Artisan Seed Crackers (150g)", "GROC-SNK-005", "071234560037", 4.19, 2.00, 22, 6, "box", "/static/images/products/crackers.svg"),
            ]

            product_objs = []
            for cat_name, name, sku, barcode, price, cost, stock, threshold, unit, img in products_def:
                category = cat_map[cat_name]
                prod, _ = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        "name": name,
                        "barcode": barcode,
                        "category": category,
                        "price": Decimal(str(price)),
                        "cost": Decimal(str(cost)),
                        "stock": stock,
                        "low_stock_threshold": threshold,
                        "unit": unit,
                        "image_url": img,
                        "is_active": True,
                    }
                )
                product_objs.append(prod)

            self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(product_objs)} Grocery Products with images & barcodes"))

            # 6. Grocery Customers with Loyalty Tiers
            customers_def = [
                ("Walk-in Customer", None, 0, "Default walk-in grocery shopper"),
                ("Emma Watson", "+1 (555) 234-5678", 540, "Platinum VIP — Regular weekly organic grocery buyer"),
                ("David Miller", "+1 (555) 345-6789", 290, "Gold Member — Buys fresh bakery and espresso daily"),
                ("Sophia Chen", "+1 (555) 456-7890", 175, "Silver Member — Prefers gluten-free and vegan produce"),
                ("Liam Johnson", "+1 (555) 567-8901", 85, "Bronze Member — Weekend family grocery shopper"),
                ("Olivia Taylor", "+1 (555) 678-9012", 340, "Gold Member — Frequent fresh seafood & pantry customer"),
                ("James Wilson", "+1 (555) 789-0123", 130, "Silver Member — Artisan bread & dairy subscriber"),
            ]

            cust_map = {}
            for name, phone, pts, note in customers_def:
                cust, _ = Customer.objects.update_or_create(
                    name=name,
                    defaults={
                        "phone": phone,
                        "loyalty_points": pts,
                        "note": note,
                    }
                )
                cust_map[name] = cust

            self.stdout.write(self.style.SUCCESS(f"✓ Seeded {len(cust_map)} Grocery Customers with Loyalty Tiers"))

            # 7. Realtime Production Scenario: Realistic Sales Transactions
            # We seed ~35 orders spanning the last 7 days through today with realistic time distribution
            # Peak retail hours: 10:00-13:00 (Lunch rush) and 16:30-19:30 (Evening dinner grocery rush)
            self.stdout.write(self.style.NOTICE("🛒 Generating realistic sales scenario across the last 7 days..."))

            # Clear previous test orders to prevent duplicate data
            Order.objects.all().delete()

            now = datetime.now(timezone.utc)
            tax_rate = Decimal("7.50")
            cashiers = ["Sarah Adams", "Store Manager"]
            payment_methods = ["card", "card", "card", "cash", "cash", "wallet"]

            # Sample grocery basket templates
            baskets = [
                ["GROC-PRD-001", "GROC-PRD-004", "GROC-DAI-001", "GROC-BAK-001"], # Avocados + Spinach + Milk + Sourdough
                ["GROC-DAI-002", "GROC-DAI-005", "GROC-BAK-002", "GROC-BEV-001"], # Eggs + Butter + Croissants + Orange Juice
                ["GROC-MEA-001", "GROC-PAN-001", "GROC-PRD-005", "GROC-PAN-002"], # Salmon + Olive Oil + Tomatoes + Pasta
                ["GROC-MEA-002", "GROC-PAN-005", "GROC-PRD-006", "GROC-BEV-004"], # Chicken + Basmati Rice + Cucumber + Green Tea
                ["GROC-PRD-003", "GROC-DAI-003", "GROC-PAN-004", "GROC-PAN-006"], # Bananas + Yogurt + Oats + Raw Honey
                ["GROC-BEV-002", "GROC-DAI-006", "GROC-SNK-003", "GROC-BAK-003"], # Coffee + Almond Milk + Dark Chocolate + Whole Wheat
                ["GROC-SNK-001", "GROC-BEV-003", "GROC-SNK-002", "GROC-SNK-005"], # Chips + Sparkling Water + Pistachios + Crackers
                ["GROC-MEA-004", "GROC-DAI-002", "GROC-BAK-004", "GROC-DAI-004"], # Bacon + Eggs + Brioche Buns + Cheddar
                ["GROC-PRD-002", "GROC-DAI-001", "GROC-SNK-004"],                 # Apples + Milk + Medjool Dates
                ["GROC-MEA-003", "GROC-BAK-004", "GROC-DAI-004", "GROC-PRD-005"], # Ground Beef + Buns + Cheddar + Tomatoes
            ]

            order_count = 0
            order_sequence = 10001
            all_prods_dict = {p.sku: p for p in product_objs}
            cust_list = list(cust_map.values())

            # Generate orders for past 6 days + today
            for day_offset in range(6, -1, -1):
                day_date = (now - timedelta(days=day_offset)).date()
                
                # Higher volume on today and weekends
                num_orders_for_day = 6 if day_offset == 0 else random.randint(3, 5)

                for _ in range(num_orders_for_day):
                    order_sequence += 1
                    order_count += 1
                    order_number = f"ORD-{order_sequence}"

                    # Random hour reflecting peak retail shopping times
                    if random.random() < 0.4:
                        hour = random.randint(10, 13) # Lunch rush
                    elif random.random() < 0.7:
                        hour = random.randint(16, 19) # Evening rush
                    else:
                        hour = random.randint(9, 20)
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    
                    order_time = datetime(
                        day_date.year, day_date.month, day_date.day,
                        hour, minute, second, tzinfo=timezone.utc
                    )

                    # Pick customer
                    customer = random.choice(cust_list)
                    cashier = random.choice(cashiers)
                    pay_method = random.choice(payment_methods)

                    # Pick items
                    basket_skus = random.choice(baskets)
                    # Randomize item quantities (1 to 3)
                    selected_items = []
                    subtotal = Decimal("0.00")

                    for sku in basket_skus:
                        prod = all_prods_dict.get(sku)
                        if prod:
                            qty = 1 if prod.price > 8 else random.choice([1, 1, 2, 3])
                            line_subtotal = round(prod.price * qty, 2)
                            subtotal += line_subtotal
                            selected_items.append((prod, qty, line_subtotal))

                    tax = round(subtotal * (tax_rate / Decimal("100")), 2)
                    discount = Decimal("0.00")
                    if customer.name != "Walk-in Customer" and random.random() < 0.25:
                        discount = Decimal(str(random.choice([1.00, 2.00, 3.50])))

                    total = max(Decimal("0.00"), subtotal + tax - discount)

                    order = Order.objects.create(
                        order_number=order_number,
                        customer=customer if customer.name != "Walk-in Customer" else None,
                        cashier_name=cashier,
                        subtotal=subtotal,
                        tax_rate=tax_rate,
                        tax=tax,
                        discount=discount,
                        total=total,
                        payment_method=pay_method,
                        payment_status="paid",
                        status="completed",
                        note="In-Store Grocery POS Checkout",
                    )

                    # Override auto_now_add with specific historical timestamp
                    Order.objects.filter(id=order.id).update(created_at=order_time)

                    # Create order items
                    for prod, qty, line_subtotal in selected_items:
                        OrderItem.objects.create(
                            order=order,
                            product=prod,
                            name=prod.name,
                            price=prod.price,
                            cost=prod.cost,
                            quantity=qty,
                            subtotal=line_subtotal,
                        )

                    # Update customer lifetime stats
                    if customer.name != "Walk-in Customer":
                        customer.total_spent = Decimal(str(customer.total_spent)) + total
                        customer.orders_count += 1
                        customer.loyalty_points += int(total)
                        customer.save(update_fields=["total_spent", "orders_count", "loyalty_points"])

            self.stdout.write(self.style.SUCCESS(f"✓ Seeded {order_count} realistic grocery orders across the week"))

        self.stdout.write(self.style.SUCCESS("\n🎉 Realtime Production Scenario & Grocery Seeding Complete!"))

