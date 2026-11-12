import os
import uuid
from django.conf import settings as django_settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db.models import Count, F, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from apps.core.utils import csv_response, login_required_pos, parse_float, parse_int, render_pos
from apps.inventory.models import Category, Product


def _handle_product_image_upload(uploaded_file):
    if not uploaded_file:
        return None
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif"]:
        ext = ".jpg"
    filename = f"prod_{uuid.uuid4().hex[:12]}{ext}"
    rel_path = os.path.join("products", filename)
    saved_path = default_storage.save(rel_path, uploaded_file)
    return f"{django_settings.MEDIA_URL.rstrip('/')}/{saved_path.replace(os.sep, '/')}"


@login_required_pos
def products_view(request):
    categories = Category.objects.annotate(product_count=Count("products")).order_name_asc = Category.objects.annotate(product_count=Count("products")).order_by("name")
    products = Product.objects.select_related("category").order_by("name")

    if request.GET.get("export") == "csv":
        cols = [
            ("name", "Name"), ("sku", "SKU"), ("barcode", "Barcode"),
            ("category_name", "Category"), ("price", "Price"), ("cost", "Cost"),
            ("margin", "Margin %"), ("stock", "Stock"), ("stock_value", "Stock Value"),
            ("status_str", "Status")
        ]
        rows = []
        for p in products:
            rows.append({
                "name": p.name,
                "sku": p.sku,
                "barcode": p.barcode or "",
                "category_name": p.category.name if p.category else "",
                "price": f"{float(p.price):.2f}",
                "cost": f"{float(p.cost):.2f}",
                "margin": f"{p.margin:.1f}",
                "stock": p.stock,
                "stock_value": f"{p.stock_value:.2f}",
                "status_str": "Active" if p.is_active else "Inactive",
            })
        return csv_response("products.csv", cols, rows)

    total_value = sum(float(p.cost) * p.stock for p in products)
    retail_value = sum(float(p.price) * p.stock for p in products)

    return render_pos(
        request,
        "products.html",
        {
            "active_view": "products",
            "categories": categories,
            "products": products,
            "total_value": total_value,
            "retail_value": retail_value,
            "potential_profit": retail_value - total_value,
        },
    )


@csrf_exempt
@login_required_pos
def products_new(request):
    category_id = request.POST.get("category_id")
    category = get_object_or_404(Category, id=category_id)

    name = request.POST.get("name", "").strip()
    sku = request.POST.get("sku", "").strip()
    barcode = request.POST.get("barcode", "").strip() or None
    description = request.POST.get("description", "").strip() or None
    price = parse_float(request.POST.get("price"), 0.0)
    cost = parse_float(request.POST.get("cost"), 0.0)
    stock = parse_int(request.POST.get("stock"), 0)
    low_stock_threshold = parse_int(request.POST.get("low_stock_threshold"), 10)
    unit = request.POST.get("unit", "pcs")
    is_active = request.POST.get("is_active") in ("on", "true", "1")

    if Product.objects.filter(sku__iexact=sku).exists():
        messages.error(request, f"Product SKU '{sku}' already exists")
        return redirect("/products")

    image_url = None
    if request.FILES.get("image"):
        image_url = _handle_product_image_upload(request.FILES.get("image"))
    elif request.POST.get("image_url", "").strip():
        image_url = request.POST.get("image_url").strip()

    product = Product.objects.create(
        name=name,
        sku=sku,
        barcode=barcode,
        description=description,
        category=category,
        price=price,
        cost=cost,
        stock=stock,
        low_stock_threshold=low_stock_threshold,
        unit=unit,
        image_url=image_url,
        is_active=is_active,
    )
    messages.success(request, f"Product '{name}' created successfully")
    return redirect("/products")


@csrf_exempt
@login_required_pos
def products_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    category_id = request.POST.get("category_id")
    if category_id:
        product.category = get_object_or_404(Category, id=category_id)

    sku = request.POST.get("sku", "").strip()
    if Product.objects.filter(sku__iexact=sku).exclude(id=product_id).exists():
        messages.error(request, f"SKU '{sku}' already in use")
        return redirect("/products")

    product.name = request.POST.get("name", product.name).strip()
    product.sku = sku
    product.barcode = request.POST.get("barcode", "").strip() or None
    product.description = request.POST.get("description", "").strip() or None
    product.price = parse_float(request.POST.get("price"), float(product.price))
    product.cost = parse_float(request.POST.get("cost"), float(product.cost))
    product.stock = parse_int(request.POST.get("stock"), product.stock)
    product.low_stock_threshold = parse_int(request.POST.get("low_stock_threshold"), product.low_stock_threshold)
    product.unit = request.POST.get("unit", product.unit)
    product.is_active = request.POST.get("is_active") in ("on", "true", "1")

    if request.FILES.get("image"):
        product.image_url = _handle_product_image_upload(request.FILES.get("image"))
    elif request.POST.get("remove_image") in ("1", "true", "on"):
        product.image_url = None
    elif request.POST.get("image_url") is not None and request.POST.get("image_url").strip():
        product.image_url = request.POST.get("image_url").strip()

    product.save()

    messages.success(request, f"Product '{product.name}' updated")
    return redirect("/products")


@csrf_exempt
@login_required_pos
def products_delete(request, product_id):
    Product.objects.filter(id=product_id).delete()
    messages.success(request, "Product deleted")
    return redirect("/products")


@csrf_exempt
@login_required_pos
def categories_new(request):
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip() or None
    color = request.POST.get("color", "#10b981")

    if not name:
        messages.error(request, "Category name is required")
        return redirect("/products")

    if Category.objects.filter(name__iexact=name).exists():
        messages.error(request, "Category already exists")
        return redirect("/products")

    Category.objects.create(name=name, description=description, color=color)
    messages.success(request, "Category created")
    return redirect("/products")


@csrf_exempt
@login_required_pos
def categories_delete(request, cat_id):
    category = get_object_or_404(Category, id=cat_id)
    count = category.products.count()
    if count > 0:
        messages.error(request, f"Cannot delete: {count} products still in this category")
    else:
        category.delete()
        messages.success(request, "Category deleted")
    return redirect("/products")


@login_required_pos
def inventory_view(request):
    products = Product.objects.select_related("category").order_by("name")
    categories = Category.objects.all().order_by("name")

    total_stock = sum(p.stock for p in products)
    total_value = sum(float(p.cost) * p.stock for p in products)
    out_of_stock = sum(1 for p in products if p.stock == 0)
    low_count = sum(1 for p in products if 0 < p.stock <= p.low_stock_threshold)

    if request.GET.get("export") == "csv":
        cols = [
            ("name", "Name"), ("sku", "SKU"), ("category_name", "Category"),
            ("stock", "Current Stock"), ("low_stock_threshold", "Threshold"),
            ("stock_value", "Stock Value"), ("status", "Status")
        ]
        rows = []
        for p in products:
            if p.stock == 0:
                status = "Out of Stock"
            elif p.stock <= p.low_stock_threshold:
                status = "Low Stock"
            elif p.stock > 200:
                status = "Overstock"
            else:
                status = "Healthy"

            rows.append({
                "name": p.name,
                "sku": p.sku,
                "category_name": p.category.name if p.category else "",
                "stock": p.stock,
                "low_stock_threshold": p.low_stock_threshold,
                "stock_value": f"{p.stock_value:.2f}",
                "status": status,
            })
        return csv_response("inventory.csv", cols, rows)

    # Category distribution
    cat_dist = []
    for c in categories:
        prods = [p for p in products if p.category_id == c.id]
        val = sum(float(p.cost) * p.stock for p in prods)
        items = sum(p.stock for p in prods)
        if items > 0 or val > 0:
            cat_dist.append({
                "name": c.name,
                "color": c.color,
                "value": round(val, 2),
                "items": items,
            })
    cat_dist.sort(key=lambda x: x["value"], reverse=True)

    return render_pos(
        request,
        "inventory.html",
        {
            "active_view": "inventory",
            "products": products,
            "categories": categories,
            "total_stock": total_stock,
            "total_value": total_value,
            "out_of_stock": out_of_stock,
            "low_count": low_count,
            "category_dist": cat_dist,
        },
    )


@csrf_exempt
@login_required_pos
def inventory_adjust(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    adjust_type = request.POST.get("type", "add")
    amount = parse_int(request.POST.get("amount"), 0)
    if amount < 0:
        amount = 0

    old_stock = product.stock
    if adjust_type == "add":
        new_stock = old_stock + amount
    elif adjust_type == "remove":
        new_stock = max(0, old_stock - amount)
    else:  # set
        new_stock = amount

    product.stock = new_stock
    product.save()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse({
            "success": True,
            "product_id": str(product.id),
            "name": product.name,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "unit": product.unit,
            "is_low": product.is_low,
            "stock_value": float(product.stock_value),
            "message": f"Stock adjusted: {old_stock} → {new_stock} {product.unit}",
        })

    next_url = request.POST.get("next") or request.GET.get("next") or "/products"
    messages.success(request, f"Stock adjusted for '{product.name}': {old_stock} → {new_stock} {product.unit}")
    return redirect(next_url)


@login_required_pos
def product_by_barcode(request, barcode):
    p = Product.objects.filter(barcode=barcode, is_active=True).first()
    if not p:
        return JsonResponse({"error": "Product not found"}, status=404)
    return JsonResponse({
        "id": str(p.id),
        "name": p.name,
        "price": float(p.price),
        "cost": float(p.cost),
        "stock": p.stock,
        "unit": p.unit,
    })

