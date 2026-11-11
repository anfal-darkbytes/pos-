from datetime import datetime, timedelta, timezone
from django.db.models import Count, F, Q, Sum
from apps.core.models import StoreSettings
from apps.core.utils import get_date_range, login_required_pos, parse_int, render_pos
from apps.inventory.models import Category, Product
from apps.sales.models import Order, OrderItem


@login_required_pos
def dashboard(request):
    settings = StoreSettings.get_settings()
    now = datetime.now(timezone.utc)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    date_from, date_to = get_date_range(request)

    today_orders = list(Order.objects.filter(created_at__gte=today_start).prefetch_related("items"))
    yesterday_orders = list(Order.objects.filter(created_at__gte=yesterday_start, created_at__lt=today_start))
    week_orders = list(Order.objects.filter(created_at__gte=week_start))
    month_orders = list(Order.objects.filter(created_at__gte=month_start))

    today_revenue = sum(float(o.total) for o in today_orders)
    yesterday_revenue = sum(float(o.total) for o in yesterday_orders)
    week_revenue = sum(float(o.total) for o in week_orders)
    month_revenue = sum(float(o.total) for o in month_orders)

    revenue_change = (
        ((today_revenue - yesterday_revenue) / yesterday_revenue * 100)
        if yesterday_revenue > 0
        else 0.0
    )

    today_items = sum(
        sum(it.quantity for it in o.items.all()) for o in today_orders
    )

    products = list(Product.objects.select_related("category").all())
    inventory_value = sum(float(p.cost) * p.stock for p in products)
    low_stock = [p for p in products if p.stock <= p.low_stock_threshold][:6]

    range_orders = list(
        Order.objects.select_related("customer")
        .prefetch_related("items__product__category")
        .filter(created_at__gte=date_from, created_at__lte=date_to)
        .order_by("created_at")
    )

    recent_orders = list(
        Order.objects.select_related("customer")
        .prefetch_related("items")
        .filter(created_at__gte=date_from, created_at__lte=date_to)
        .order_by("-created_at")[:8]
    )

    # Hourly distribution for today
    hourly_data = [{"hour": f"{h:02d}:00", "sales": 0.0, "orders": 0} for h in range(24)]
    for o in today_orders:
        if o.created_at:
            h = o.created_at.hour
            hourly_data[h]["sales"] += float(o.total)
            hourly_data[h]["orders"] += 1
    hourly_filtered = [h for h in hourly_data if h["orders"] > 0]

    # Daily distribution for period
    daily_map = {}
    for o in range_orders:
        if not o.created_at:
            continue
        key = o.created_at.strftime("%Y-%m-%d")
        if key not in daily_map:
            daily_map[key] = {
                "date": key,
                "label": o.created_at.strftime("%b %d"),
                "sales": 0.0,
                "orders": 0,
            }
        daily_map[key]["sales"] += float(o.total)
        daily_map[key]["orders"] += 1

    # Top products in period
    order_items_range = OrderItem.objects.filter(
        order__created_at__gte=date_from,
        order__created_at__lte=date_to,
    ).select_related("product__category")

    prod_map = {}
    for it in order_items_range:
        pid = str(it.product_id)
        if pid not in prod_map:
            cat_name = it.product.category.name if it.product and it.product.category else "—"
            prod_map[pid] = {
                "name": it.name,
                "category": cat_name,
                "revenue": 0.0,
                "quantity": 0,
            }
        prod_map[pid]["revenue"] += float(it.subtotal)
        prod_map[pid]["quantity"] += it.quantity
    top_products = sorted(prod_map.values(), key=lambda x: x["revenue"], reverse=True)[:5]

    # Category breakdown
    cat_map = {}
    for it in order_items_range:
        if it.product and it.product.category:
            cid = str(it.product.category_id)
            if cid not in cat_map:
                cat_map[cid] = {
                    "name": it.product.category.name,
                    "color": it.product.category.color,
                    "revenue": 0.0,
                    "quantity": 0,
                }
            cat_map[cid]["revenue"] += float(it.subtotal)
            cat_map[cid]["quantity"] += it.quantity
    category_breakdown = sorted(cat_map.values(), key=lambda x: x["revenue"], reverse=True)
    for c in category_breakdown:
        c["revenue"] = round(c["revenue"], 2)

    # Payment breakdown
    pay_map = {}
    for o in range_orders:
        pm = o.payment_method or "cash"
        if pm not in pay_map:
            pay_map[pm] = {"payment_method": pm, "count": 0, "total": 0.0}
        pay_map[pm]["count"] += 1
        pay_map[pm]["total"] += float(o.total)
    payment_breakdown = list(pay_map.values())
    for p in payment_breakdown:
        p["total"] = round(p["total"], 2)

    stats = {
        "today_revenue": round(today_revenue, 2),
        "yesterday_revenue": round(yesterday_revenue, 2),
        "revenue_change": round(revenue_change, 2),
        "today_orders": len(today_orders),
        "today_items": today_items,
        "week_revenue": round(week_revenue, 2),
        "month_revenue": round(month_revenue, 2),
        "week_orders": len(week_orders),
        "month_orders": len(month_orders),
        "period_revenue": round(sum(float(o.total) for o in range_orders), 2),
        "period_orders": len(range_orders),
        "inventory_value": round(inventory_value, 2),
        "total_products": len(products),
        "active_products": sum(1 for p in products if p.is_active),
        "low_stock_count": len([p for p in products if p.is_low]),
    }

    return render_pos(
        request,
        "dashboard.html",
        {
            "active_view": "dashboard",
            "settings": settings,
            "stats": stats,
            "hourly_data": hourly_filtered,
            "daily_sales": list(daily_map.values()),
            "top_products": top_products,
            "category_breakdown": category_breakdown,
            "payment_breakdown": payment_breakdown,
            "recent_orders": recent_orders,
            "low_stock": low_stock,
            "date_from": date_from.strftime("%Y-%m-%d") if hasattr(date_from, "strftime") else str(date_from)[:10],
            "date_to": date_to.strftime("%Y-%m-%d") if hasattr(date_to, "strftime") else str(date_to)[:10],
        },
    )


@login_required_pos
def reports_view(request):
    settings = StoreSettings.get_settings()
    days = parse_int(request.GET.get("days"), 0)
    now = datetime.now(timezone.utc)

    if 0 < days <= 365:
        cutoff = now - timedelta(days=days)
        date_from = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        date_to = now.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%dT%H:%M:%S")
    else:
        date_from, date_to = get_date_range(request)

    orders = list(
        Order.objects.select_related("customer")
        .prefetch_related("items__product__category")
        .filter(created_at__gte=date_from, created_at__lte=date_to)
        .order_by("created_at")
    )

    daily_map = {}
    for o in orders:
        if not o.created_at:
            continue
        key = o.created_at.strftime("%Y-%m-%d")
        if key not in daily_map:
            daily_map[key] = {
                "date": key,
                "label": o.created_at.strftime("%b %d"),
                "sales": 0.0,
                "orders": 0,
                "profit": 0.0,
            }
        daily_map[key]["sales"] += float(o.total)
        daily_map[key]["orders"] += 1
        for it in o.items.all():
            daily_map[key]["profit"] += float((it.price - it.cost) * it.quantity)

    daily_sales = list(daily_map.values())
    for d in daily_sales:
        d["sales"] = round(d["sales"], 2)
        d["profit"] = round(d["profit"], 2)

    order_items = OrderItem.objects.filter(
        order__created_at__gte=date_from,
        order__created_at__lte=date_to,
    ).select_related("product__category")

    prod_map = {}
    for it in order_items:
        pid = str(it.product_id)
        if pid not in prod_map:
            cat_name = it.product.category.name if it.product and it.product.category else "—"
            prod_map[pid] = {
                "product_id": pid,
                "name": it.name,
                "price": float(it.price),
                "cost": float(it.cost),
                "quantity": 0,
                "revenue": 0.0,
                "profit": 0.0,
                "category": cat_name,
            }
        prod_map[pid]["quantity"] += it.quantity
        prod_map[pid]["revenue"] += float(it.subtotal)
        prod_map[pid]["profit"] += float((it.price - it.cost) * it.quantity)

    top_products = list(prod_map.values())
    for p in top_products:
        p["revenue"] = round(p["revenue"], 2)
        p["profit"] = round(p["profit"], 2)
        p["margin"] = (p["profit"] / p["revenue"] * 100) if p["revenue"] > 0 else 0.0
    top_products.sort(key=lambda x: x["revenue"], reverse=True)

    cat_map = {}
    for it in order_items:
        if it.product and it.product.category:
            cid = str(it.product.category_id)
            if cid not in cat_map:
                cat_map[cid] = {
                    "name": it.product.category.name,
                    "color": it.product.category.color,
                    "revenue": 0.0,
                    "quantity": 0,
                    "profit": 0.0,
                }
            cat_map[cid]["revenue"] += float(it.subtotal)
            cat_map[cid]["quantity"] += it.quantity
            cat_map[cid]["profit"] += float((it.price - it.cost) * it.quantity)

    category_breakdown = list(cat_map.values())
    for c in category_breakdown:
        c["revenue"] = round(c["revenue"], 2)
        c["profit"] = round(c["profit"], 2)
    category_breakdown.sort(key=lambda x: x["revenue"], reverse=True)

    pay_map = {}
    for o in orders:
        pm = o.payment_method or "cash"
        if pm not in pay_map:
            pay_map[pm] = {"payment_method": pm, "count": 0, "total": 0.0}
        pay_map[pm]["count"] += 1
        pay_map[pm]["total"] += float(o.total)
    payment_breakdown = list(pay_map.values())
    for p in payment_breakdown:
        p["total"] = round(p["total"], 2)

    total_revenue = sum(float(o.total) for o in orders)
    total_profit = sum(
        sum(float((it.price - it.cost) * it.quantity) for it in o.items.all()) for o in orders
    )
    total_items = sum(
        sum(it.quantity for it in o.items.all()) for o in orders
    )

    summary = {
        "total_revenue": round(total_revenue, 2),
        "total_profit": round(total_profit, 2),
        "total_orders": len(orders),
        "total_items": total_items,
        "avg_order_value": round(total_revenue / len(orders), 2) if orders else 0.0,
        "profit_margin": round(total_profit / total_revenue * 100, 2) if total_revenue > 0 else 0.0,
    }

    return render_pos(
        request,
        "reports.html",
        {
            "active_view": "reports",
            "settings": settings,
            "days": days,
            "date_from": date_from.strftime("%Y-%m-%d") if hasattr(date_from, "strftime") else str(date_from)[:10],
            "date_to": date_to.strftime("%Y-%m-%d") if hasattr(date_to, "strftime") else str(date_to)[:10],
            "summary": summary,
            "daily_sales": daily_sales,
            "top_products": top_products[:10],
            "category_breakdown": category_breakdown,
            "payment_breakdown": payment_breakdown,
        },
    )
