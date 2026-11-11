from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from apps.core.utils import csv_response, login_required_pos, parse_int, render_pos
from apps.customers.models import Customer


@login_required_pos
def customers_view(request):
    search = request.GET.get("search", "").strip()
    if search:
        customers = Customer.objects.filter(
            Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
        ).order_by("-created_at")
    else:
        customers = Customer.objects.all().order_by("-created_at")

    if request.GET.get("export") == "csv":
        cols = [
            ("name", "Name"), ("email", "Email"), ("phone", "Phone"),
            ("address", "Address"), ("loyalty_points", "Points"),
            ("total_spent", "Total Spent"), ("orders_count", "Orders"),
            ("tier", "Tier"), ("joined_str", "Joined")
        ]
        rows = []
        for c in customers:
            rows.append({
                "name": c.name,
                "email": c.email or "",
                "phone": c.phone or "",
                "address": c.address or "",
                "loyalty_points": c.loyalty_points,
                "total_spent": f"{float(c.total_spent):.2f}",
                "orders_count": c.orders_count,
                "tier": c.tier,
                "joined_str": c.created_at.strftime("%b %d, %Y") if c.created_at else "",
            })
        return csv_response("customers.csv", cols, rows)

    total_loyalty = sum(c.loyalty_points for c in customers)
    total_spent = sum(float(c.total_spent) for c in customers)
    avg_spent = (total_spent / len(customers)) if customers else 0.0
    real_count = sum(1 for c in customers if c.name != "Walk-in Customer")

    return render_pos(
        request,
        "customers.html",
        {
            "active_view": "customers",
            "customers": customers,
            "search": search,
            "total_loyalty": total_loyalty,
            "total_spent": total_spent,
            "avg_spent": avg_spent,
            "real_count": real_count,
        },
    )


@csrf_exempt
@login_required_pos
def customers_new(request):
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip() or None
    phone = request.POST.get("phone", "").strip() or None
    address = request.POST.get("address", "").strip() or None
    loyalty_points = parse_int(request.POST.get("loyalty_points"), 0)
    note = request.POST.get("note", "").strip() or None

    if not name:
        messages.error(request, "Customer name is required")
        return redirect("/customers")

    Customer.objects.create(
        name=name,
        email=email,
        phone=phone,
        address=address,
        loyalty_points=loyalty_points,
        note=note,
    )
    messages.success(request, "Customer added")
    return redirect("/customers")


@csrf_exempt
@login_required_pos
def customers_edit(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Customer name is required")
        return redirect("/customers")

    customer.name = name
    customer.email = request.POST.get("email", "").strip() or None
    customer.phone = request.POST.get("phone", "").strip() or None
    customer.address = request.POST.get("address", "").strip() or None
    customer.loyalty_points = parse_int(request.POST.get("loyalty_points"), customer.loyalty_points)
    customer.note = request.POST.get("note", "").strip() or None
    customer.save()

    messages.success(request, "Customer updated")
    return redirect("/customers")


@csrf_exempt
@login_required_pos
def customers_delete(request, customer_id):
    Customer.objects.filter(id=customer_id).delete()
    messages.success(request, "Customer deleted")
    return redirect("/customers")

