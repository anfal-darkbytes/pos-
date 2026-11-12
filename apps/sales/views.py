import json
from datetime import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import StoreSettings, PaymentAccount
from apps.core.utils import csv_response, get_date_range, login_required_pos, parse_float, parse_int, render_pos
from apps.customers.models import Customer
from apps.inventory.models import Category, Product
from apps.sales.models import Order, OrderItem, OrderPayment


@login_required_pos
def pos_terminal(request):
    settings = StoreSettings.get_settings()
    categories = Category.objects.all().order_by("name")
    products = Product.objects.filter(is_active=True).select_related("category").order_by("name")
    customers = Customer.objects.all().order_by("name")
    PaymentAccount.seed_default_accounts_if_empty()
    payment_accounts = PaymentAccount.objects.filter(is_active=True).order_by("category", "name")

    return render_pos(
        request,
        "pos.html",
        {
            "active_view": "pos",
            "settings": settings,
            "categories": categories,
            "products": products,
            "customers": customers,
            "payment_accounts": payment_accounts,
        },
    )


def process_order_creation(data, request_user=None):
    """
    Core order processing logic shared by live checkout and offline sync engine.
    Ensures idempotency via client_id, atomic stock deductions, and conflict policies.
    """
    client_id = data.get("client_id") or data.get("idempotency_key") or None
    if client_id:
        existing = Order.objects.filter(client_id=client_id).select_related("customer").prefetch_related("items").first()
        if existing:
            settings = StoreSettings.get_settings()
            order_data = existing.to_dict()
            order_data["currency_symbol"] = settings.currency_symbol
            return {
                "order": order_data,
                "idempotent_replay": True,
                "client_id": client_id,
                "conflicts": [],
            }

    items = data.get("items", [])
    if not items:
        raise ValueError("Cart is empty")

    settings = StoreSettings.get_settings()
    tax_rate_val = parse_float(data.get("tax_rate"), float(settings.tax_rate))
    discount_val = parse_float(data.get("discount"), 0.0)
    payment_method = data.get("payment_method", "cash")
    customer_id = data.get("customer_id") or None
    cashier_name = data.get("cashier_name") or getattr(request_user, "name", None) or getattr(request_user, "username", "Cashier") or "Cashier"
    is_offline_sync = bool(data.get("is_offline_sync") or data.get("is_offline"))

    customer = None
    if customer_id:
        customer = Customer.objects.filter(id=customer_id).first()

    conflicts = []
    with transaction.atomic():
        subtotal = Decimal("0.00")
        validated_items = []

        for item in items:
            prod_id = item.get("productId") or item.get("product_id")
            product = Product.objects.select_for_update().filter(id=prod_id).first()
            if not product:
                raise ValueError(f"Product not found: {prod_id}")

            qty = int(item.get("quantity", 1))
            if qty <= 0:
                continue

            price_val = parse_float(item.get("price"), float(product.price))
            item_price = Decimal(str(price_val)).quantize(Decimal("0.01"))
            cost_val = Decimal(str(product.cost)).quantize(Decimal("0.01"))

            # Inventory conflict detection
            if product.stock < qty:
                if is_offline_sync:
                    deficit = qty - product.stock
                    conflicts.append({
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "type": "inventory_deficit",
                        "deficit": deficit,
                        "message": f"Product '{product.name}' was oversold by {deficit} unit(s) during offline operation."
                    })
                else:
                    raise ValueError(f"Insufficient stock for {product.name} (Available: {product.stock}, Requested: {qty})")

            line_subtotal = (item_price * qty).quantize(Decimal("0.01"))
            subtotal += line_subtotal
            validated_items.append({
                "product": product,
                "name": item.get("name") or product.name,
                "price": item_price,
                "cost": cost_val,
                "quantity": qty,
                "subtotal": line_subtotal,
            })

        subtotal = subtotal.quantize(Decimal("0.01"))
        tax = (subtotal * Decimal(str(tax_rate_val)) / Decimal("100")).quantize(Decimal("0.01"))
        discount = Decimal(str(discount_val)).quantize(Decimal("0.01"))
        total = (subtotal + tax - discount).quantize(Decimal("0.01"))

        # Sequential collision-free order numbering
        nums = [
            int(n.replace("ORD-", ""))
            for n in Order.objects.values_list("order_number", flat=True)
            if n.startswith("ORD-") and n.replace("ORD-", "").isdigit()
        ]
        next_seq = (max(nums) + 1) if nums else 10001
        order_number = f"ORD-{next_seq}"
        while Order.objects.filter(order_number=order_number).exists():
            next_seq += 1
            order_number = f"ORD-{next_seq}"

        note_content = (data.get("note") or "").strip()
        if conflicts:
            conflict_notes = "; ".join([c["message"] for c in conflicts])
            note_content = f"{note_content} [Sync: {conflict_notes}]".strip()

        # Process payment allocations (Full payment or Split payment)
        raw_payments = data.get("payments", [])
        if isinstance(raw_payments, str):
            try:
                raw_payments = json.loads(raw_payments)
            except Exception:
                raw_payments = []

        is_split = payment_method == "split" or len(raw_payments) > 1

        if not raw_payments or len(raw_payments) == 0:
            if payment_method == "cash":
                tendered_val = parse_float(data.get("paid_amount"), float(total))
                change_val = max(0.0, tendered_val - float(total)) if tendered_val >= float(total) else 0.0
                raw_payments = [{
                    "payment_method": "cash",
                    "amount": float(total),
                    "tendered": tendered_val,
                    "change": change_val,
                    "account_name": "",
                    "reference": "",
                }]
            elif payment_method == "bank":
                raw_payments = [{
                    "payment_method": "bank",
                    "amount": float(total),
                    "account_id": data.get("bank_account_id"),
                    "account_name": data.get("bank_account_name") or data.get("account_name") or "",
                    "reference": data.get("bank_ref") or data.get("reference") or "",
                }]
            elif payment_method == "wallet":
                raw_payments = [{
                    "payment_method": "wallet",
                    "amount": float(total),
                    "account_id": data.get("wallet_account_id"),
                    "account_name": data.get("wallet_account_name") or data.get("account_name") or "",
                    "reference": data.get("wallet_ref") or data.get("reference") or "",
                }]
            else:
                raw_payments = [{
                    "payment_method": payment_method or "cash",
                    "amount": float(total),
                }]

        if is_split:
            payment_method = "split"

        order = Order(
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
            note=note_content or None,
            client_id=client_id,
            is_offline_sync=is_offline_sync,
            synced_at=timezone.now() if is_offline_sync else None,
        )
        order.save()

        # Create OrderPayment line items
        split_summary_parts = []
        for p in raw_payments:
            p_method = (p.get("payment_method") or "cash").lower()
            p_amount = Decimal(str(parse_float(p.get("amount"), 0.0))).quantize(Decimal("0.01"))
            if p_amount <= 0:
                continue
            p_acc_name = (p.get("account_name") or "").strip()
            p_acc_title = (p.get("account_title") or "").strip()
            p_acc_num = (p.get("account_number") or "").strip()
            p_ref = (p.get("reference") or "").strip()
            p_tendered = Decimal(str(parse_float(p.get("tendered"), float(p_amount)))).quantize(Decimal("0.01"))
            p_change = Decimal(str(parse_float(p.get("change"), 0.0))).quantize(Decimal("0.01"))

            acc_obj = None
            acc_id = p.get("account_id")
            if acc_id:
                acc_obj = PaymentAccount.objects.filter(id=acc_id).first()
            if not acc_obj and p_acc_name:
                acc_obj = PaymentAccount.objects.filter(name__iexact=p_acc_name).first()

            if acc_obj:
                p_acc_name = acc_obj.name
                p_acc_title = p_acc_title or acc_obj.account_name
                p_acc_num = p_acc_num or acc_obj.account_number

            OrderPayment.objects.create(
                order=order,
                payment_method=p_method,
                account=acc_obj,
                account_name=p_acc_name or None,
                account_title=p_acc_title or None,
                account_number=p_acc_num or None,
                amount=p_amount,
                tendered=p_tendered,
                change=p_change,
                reference=p_ref or None,
            )
            acc_info = f" ({p_acc_name})" if p_acc_name else ""
            ref_info = f" [Ref: {p_ref}]" if p_ref else ""
            split_summary_parts.append(f"{p_method.capitalize()}{acc_info}: {settings.currency_symbol}{p_amount}{ref_info}")

        if is_split and split_summary_parts:
            split_text = "Split Tender: " + ", ".join(split_summary_parts)
            order.note = f"{order.note or ''} [{split_text}]".strip()
            order.save(update_fields=["note"])

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
            # Authoritative stock update (allows negative stock for offline audit deficit)
            vi["product"].stock -= vi["quantity"]
            vi["product"].save(update_fields=["stock"])

        if customer:
            customer.total_spent = Decimal(str(customer.total_spent)) + total
            customer.orders_count += 1
            customer.loyalty_points += int(total)
            customer.save(update_fields=["total_spent", "orders_count", "loyalty_points"])

    order_data = order.to_dict()
    order_data["currency_symbol"] = settings.currency_symbol
    return {
        "order": order_data,
        "idempotent_replay": False,
        "client_id": client_id,
        "conflicts": conflicts,
    }


@csrf_exempt
def checkout_api(request):
    """
    Creates a new order from cart JSON payload.
    Supports live online checkouts as well as single offline sync submissions with idempotency.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            data = request.POST

        result = process_order_creation(data, request_user=request.user)
        return JsonResponse(result)
    except ValueError as ve:
        return JsonResponse({"error": str(ve)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def sync_orders_api(request):
    """
    Batch synchronization endpoint for client outbox operations.
    Processes queued customer creations and orders with foreign-key dependency sequencing.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        operations = data.get("operations", [])
        synced_client_ids = []
        conflicts_all = []
        errors_all = []

        # Step 1: Process customer creations first (outbox dependency resolution)
        customer_id_map = {}
        for op in operations:
            if op.get("type") == "create_customer":
                op_payload = op.get("payload", {})
                client_cust_id = op.get("id") or op_payload.get("client_id")
                cust_name = (op_payload.get("name") or "").strip()
                if cust_name:
                    phone = (op_payload.get("phone") or "").strip() or None
                    existing_cust = None
                    if phone:
                        existing_cust = Customer.objects.filter(phone=phone).first()
                    if not existing_cust:
                        cust = Customer.objects.create(
                            name=cust_name,
                            phone=phone,
                            email=(op_payload.get("email") or "").strip() or None,
                            address=(op_payload.get("address") or "").strip() or None,
                            loyalty_points=parse_int(op_payload.get("loyalty_points"), 0),
                            note=(op_payload.get("note") or "").strip() or None,
                        )
                        customer_id_map[str(client_cust_id)] = str(cust.id)
                    else:
                        customer_id_map[str(client_cust_id)] = str(existing_cust.id)
                if client_cust_id:
                    synced_client_ids.append(client_cust_id)

        # Step 2: Process sales orders
        for op in operations:
            if op.get("type") in ("create_order", "sale"):
                op_payload = op.get("payload", {})
                client_id = op.get("id") or op_payload.get("client_id")
                op_payload["client_id"] = client_id
                op_payload["is_offline_sync"] = True

                # Remap temporary customer ID if customer was created in same offline session
                if op_payload.get("customer_id") in customer_id_map:
                    op_payload["customer_id"] = customer_id_map[op_payload["customer_id"]]

                try:
                    res = process_order_creation(op_payload, request_user=request.user)
                    if client_id:
                        synced_client_ids.append(client_id)
                    if res.get("conflicts"):
                        conflicts_all.extend(res["conflicts"])
                except Exception as op_err:
                    errors_all.append({
                        "client_id": client_id,
                        "error": str(op_err),
                    })

        return JsonResponse({
            "success": True,
            "synced": synced_client_ids,
            "conflicts": conflicts_all,
            "errors": errors_all,
            "server_time": timezone.now().isoformat(),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def sync_bootstrap_api(request):
    """
    Returns full or incremental master catalog and store configuration for IndexedDB storage.
    Supports ?since=<iso_timestamp> for delta sync.
    """
    since_str = request.GET.get("since")
    since_dt = None
    if since_str:
        try:
            since_dt = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        except Exception:
            since_dt = None

    prod_qs = Product.objects.filter(is_active=True).select_related("category")
    cat_qs = Category.objects.all()
    cust_qs = Customer.objects.all()
    PaymentAccount.seed_default_accounts_if_empty()
    acc_qs = PaymentAccount.objects.filter(is_active=True).order_by("category", "name")

    if since_dt:
        prod_qs = prod_qs.filter(updated_at__gt=since_dt)
        cat_qs = cat_qs.filter(updated_at__gt=since_dt)
        cust_qs = cust_qs.filter(updated_at__gt=since_dt)
        acc_qs = acc_qs.filter(updated_at__gt=since_dt)

    settings = StoreSettings.get_settings()
    return JsonResponse({
        "products": [p.to_dict() for p in prod_qs],
        "categories": [c.to_dict() for c in cat_qs],
        "customers": [c.to_dict() for c in cust_qs],
        "payment_accounts": [a.to_dict() for a in acc_qs],
        "settings": settings.to_dict(),
        "server_time": timezone.now().isoformat(),
        "delta": bool(since_dt),
    })


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
        if payment in ["bank", "card"]:
            qs = qs.filter(payment_method__in=["bank", "card"])
        else:
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
