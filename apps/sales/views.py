import json
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import StoreSettings
from apps.core.utils import csv_response, get_date_range, login_required_pos, parse_float, render_pos
from apps.customers.models import Customer
from apps.inventory.models import Category, Product
from apps.sales.models import Order, OrderItem


@login_required_pos
def pos_terminal(request):
    settings = StoreSettings.get_settings()
    categories = Category.objects.all().order_by("name")
    products = Product.objects.filter(is_active=True).select_related("category").order_by("name")
    customers = Customer.objects.all().order_by("name")

    return render_pos(
        request,
        "pos.html",
        {
            "active_view": "pos",
            "settings": settings,
            "categories": categories,
            "products": products,
            "customers": customers,
        },
    )


@csrf_exempt
def checkout_api(request):
    """
    Creates a new order from cart JSON payload.
    Uses atomic transaction to ensure stock and customer updates succeed together.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            data = request.POST

        items = data.get("items", [])
        if not items:
            return JsonResponse({"error": "Cart is empty"}, status=400)

        settings = StoreSettings.get_settings()
        tax_rate_val = parse_float(data.get("tax_rate"), float(settings.tax_rate))
        discount_val = parse_float(data.get("discount"), 0.0)
        payment_method = data.get("payment_method", "cash")
        customer_id = data.get("customer_id") or None
        cashier_name = data.get("cashier_name") or getattr(request.user, "name", "Cashier") or "Cashier"

        customer = None
        if customer_id:
            customer = Customer.objects.filter(id=customer_id).first()

        with transaction.atomic():
            subtotal = Decimal("0.00")
            validated_items = []

            for item in items:
                prod_id = item.get("productId")
                product = Product.objects.select_for_update().filter(id=prod_id).first()
                if not product:
                    return JsonResponse({"error": f"Product not found: {prod_id}"}, status=400)

                qty = int(item.get("quantity", 1))
                if product.stock < qty:
                    return JsonResponse({"error": f"Insufficient stock for {product.name}"}, status=400)

                line_subtotal = round(product.price * qty, 2)
                subtotal += line_subtotal
                validated_items.append({
                    "product": product,
                    "name": product.name,
                    "price": product.price,
                    "cost": product.cost,
                    "quantity": qty,
                    "subtotal": line_subtotal,
                })

            subtotal = round(subtotal, 2)
            tax = round(subtotal * Decimal(str(tax_rate_val)) / Decimal("100"), 2)
            discount = Decimal(str(discount_val))
            total = round(subtotal + tax - discount, 2)

            count = Order.objects.count()
            order_number = f"ORD-{10000 + count + 1}"

            order = Order.objects.create(
                order_number=order_number,
                customer=customer,
                cashier_name=cashier_name,
                subtotal=subtotal,
                tax_rate=Decimal(str(tax_rate_val)),
                tax=tax,
                discount=discount,
                total=total,
                payment_method=payment_method,
                payment_status="paid",
                status="completed",
                note=data.get("note") or None,
            )

            for vi in validated_items:
                OrderItem.objects.create(
                    order=order,
                    product=vi["product"],
                    name=vi["name"],
                    price=vi["price"],
                    cost=vi["cost"],
                    quantity=vi["quantity"],
                    subtotal=vi["subtotal"],
                )
                # Decrement stock
                vi["product"].stock -= vi["quantity"]
                vi["product"].save(update_fields=["stock"])

            if customer:
                customer.total_spent = Decimal(str(customer.total_spent)) + total
                customer.orders_count += 1
                customer.loyalty_points += int(total)
                customer.save(update_fields=["total_spent", "orders_count", "loyalty_points"])

        order_data = order.to_dict()
        order_data["currency_symbol"] = settings.currency_symbol

        return JsonResponse({"order": order_data})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required_pos
def orders_view(request):
    settings = StoreSettings.get_settings()
    search = request.GET.get("search", "").strip()
    payment = request.GET.get("payment", "all").strip()
    date_from, date_to = get_date_range(request)

    qs = Order.objects.select_related("customer").prefetch_related("items").filter(
        created_at__gte=date_from,
        created_at__lte=date_to,
    )

    if search:
        qs = qs.filter(Q(order_number__icontains=search) | Q(customer__name__icontains=search))

    if payment != "all":
        qs = qs.filter(payment_method=payment)

    orders = list(qs.order_by("-created_at")[:200])

    # Pre-calculate item counts for orders
    for o in orders:
        o.items_count = sum(it.quantity for it in o.items.all())

    if request.GET.get("export") == "csv":
        cols = [
            ("order_number", "Order #"), ("created_str", "Date"),
            ("customer_name", "Customer"), ("cashier_name", "Cashier"),
            ("items_count", "Items"), ("payment_method", "Payment"),
            ("subtotal", "Subtotal"), ("tax", "Tax"), ("discount", "Discount"),
            ("total", "Total")
        ]
        rows = []
        for o in orders:
            rows.append({
                "order_number": o.order_number,
                "created_str": o.created_at.strftime("%b %d, %Y %I:%M %p") if o.created_at else "",
                "customer_name": o.customer_name,
                "cashier_name": o.cashier_name,
                "items_count": o.items_count,
                "payment_method": o.payment_method,
                "subtotal": f"{float(o.subtotal):.2f}",
                "tax": f"{float(o.tax):.2f}",
                "discount": f"{float(o.discount):.2f}",
                "total": f"{float(o.total):.2f}",
            })
        return csv_response("orders.csv", cols, rows)

    total_revenue = sum(float(o.total) for o in orders)
    avg_order = (total_revenue / len(orders)) if orders else 0.0
    total_items = sum(o.items_count for o in orders)

    return render_pos(
        request,
        "orders.html",
        {
            "active_view": "orders",
            "settings": settings,
            "orders": orders,
            "search": search,
            "payment_filter": payment,
            "total_revenue": total_revenue,
            "avg_order": avg_order,
            "total_items": total_items,
            "date_from": date_from.strftime("%Y-%m-%d") if hasattr(date_from, "strftime") else str(date_from)[:10],
            "date_to": date_to.strftime("%Y-%m-%d") if hasattr(date_to, "strftime") else str(date_to)[:10],
        },
    )


@login_required_pos
def order_detail(request, order_id):
    order = Order.objects.filter(id=order_id).select_related("customer").first()
    if not order:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse(order.to_dict())


@login_required_pos
def invoices_view(request):
    settings = StoreSettings.get_settings()
    date_from, date_to = get_date_range(request)

    orders = list(
        Order.objects.select_related("customer")
        .prefetch_related("items__product__category")
        .filter(created_at__gte=date_from, created_at__lte=date_to)
        .order_by("-created_at")[:200]
    )

    for o in orders:
        o.items_count = sum(it.quantity for it in o.items.all())

    if request.GET.get("export") == "csv":
        cols = [
            ("order_number", "Invoice #"), ("created_str", "Date"),
            ("customer_name", "Customer"), ("cashier_name", "Cashier"),
            ("items_count", "Items"), ("subtotal", "Subtotal"),
            ("tax", "Tax"), ("discount", "Discount"), ("total", "Total"),
            ("payment_method", "Payment")
        ]
        rows = []
        for o in orders:
            rows.append({
                "order_number": o.order_number,
                "created_str": o.created_at.strftime("%b %d, %Y") if o.created_at else "",
                "customer_name": o.customer_name,
                "cashier_name": o.cashier_name,
                "items_count": o.items_count,
                "subtotal": f"{float(o.subtotal):.2f}",
                "tax": f"{float(o.tax):.2f}",
                "discount": f"{float(o.discount):.2f}",
                "total": f"{float(o.total):.2f}",
                "payment_method": o.payment_method,
            })
        return csv_response("invoices.csv", cols, rows)

    total_revenue = sum(float(o.total) for o in orders)
    total_orders = len(orders)
    total_items = sum(o.items_count for o in orders)

    return render_pos(
        request,
        "invoices.html",
        {
            "active_view": "invoices",
            "settings": settings,
            "orders": orders,
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_items": total_items,
            "date_from": date_from.strftime("%Y-%m-%d") if hasattr(date_from, "strftime") else str(date_from)[:10],
            "date_to": date_to.strftime("%Y-%m-%d") if hasattr(date_to, "strftime") else str(date_to)[:10],
        },
    )
