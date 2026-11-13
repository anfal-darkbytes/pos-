import json
import os

from django.conf import settings as django_settings
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import StoreSettings, PaymentAccount
from apps.core.utils import admin_required_pos, login_required_pos, parse_float, render_pos


def manifest_view(request):
    manifest_path = os.path.join(django_settings.BASE_DIR, "static", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = f.read()
        return HttpResponse(data, content_type="application/manifest+json; charset=utf-8")
    raise Http404("Manifest not found")


def service_worker_view(request):
    sw_path = os.path.join(django_settings.BASE_DIR, "static", "sw.js")
    if os.path.exists(sw_path):
        with open(sw_path, "r", encoding="utf-8") as f:
            data = f.read()
        response = HttpResponse(data, content_type="application/javascript; charset=utf-8")
        response["Service-Worker-Allowed"] = "/"
        return response
    raise Http404("Service worker not found")


def offline_view(request):
    return render_pos(request, "offline.html", {"active_view": "offline"})


SUPPORTED_CURRENCIES = [
    ("USD", "$", "US Dollar"),
    ("EUR", "€", "Euro"),
    ("GBP", "£", "British Pound"),
    ("PKR", "Rs", "Pakistani Rupee"),
    ("INR", "₹", "Indian Rupee"),
    ("AED", "AED", "UAE Dirham"),
    ("SAR", "SAR", "Saudi Riyal"),
    ("CAD", "C$", "Canadian Dollar"),
    ("AUD", "A$", "Australian Dollar"),
    ("JPY", "¥", "Japanese Yen"),
    ("CNY", "¥", "Chinese Yuan"),
    ("BDT", "৳", "Bangladeshi Taka"),
    ("TRY", "₺", "Turkish Lira"),
    ("MYR", "RM", "Malaysian Ringgit"),
    ("SGD", "S$", "Singapore Dollar"),
    ("IDR", "Rp", "Indonesian Rupiah"),
    ("PHP", "₱", "Philippine Peso"),
    ("ZAR", "R", "South African Rand"),
    ("NGN", "₦", "Nigerian Naira"),
    ("EGP", "E£", "Egyptian Pound"),
]


def api_general_settings(request):
    settings = StoreSettings.get_settings()
    return JsonResponse(settings.to_dict())


@csrf_exempt
@login_required_pos
def settings_view(request):
    settings = StoreSettings.get_settings()

    if request.method == "POST":
        settings.store_name = request.POST.get("store_name", settings.store_name)
        settings.address = request.POST.get("address", settings.address)
        settings.phone = request.POST.get("phone", settings.phone)
        settings.email = request.POST.get("email", settings.email)
        settings.tax_rate = parse_float(request.POST.get("tax_rate"), float(settings.tax_rate))
        curr_code = request.POST.get("currency", settings.currency).strip()
        curr_sym = request.POST.get("currency_symbol", "").strip()
        if curr_code:
            settings.currency = curr_code
        if curr_sym:
            settings.currency_symbol = curr_sym
        elif curr_code:
            curr_map = {c[0]: c[1] for c in SUPPORTED_CURRENCIES}
            settings.currency_symbol = curr_map.get(curr_code, settings.currency_symbol)

        settings.receipt_footer = request.POST.get("receipt_footer", settings.receipt_footer)
        settings.low_stock_alert_enabled = request.POST.get("low_stock_alert_enabled") in ("on", "true", "1")
        settings.save()

        messages.success(request, "Settings saved successfully")
        return redirect("/settings")

    PaymentAccount.seed_default_accounts_if_empty()
    payment_accounts = PaymentAccount.objects.all().order_by("category", "name")

    return render_pos(
        request,
        "settings.html",
        {
            "active_view": "settings",
            "settings": settings,
            "currencies": SUPPORTED_CURRENCIES,
            "payment_accounts": payment_accounts,
        },
    )


def api_payment_accounts(request):
    """Returns active bank accounts and mobile wallets in JSON format."""
    PaymentAccount.seed_default_accounts_if_empty()
    accounts = PaymentAccount.objects.filter(is_active=True).order_by("category", "name")
    return JsonResponse([a.to_dict() for a in accounts], safe=False)


@csrf_exempt
@login_required_pos
def payment_account_create(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    category = request.POST.get("category", "bank").strip().lower()
    if category not in ("bank", "wallet"):
        category = "bank"

    name = request.POST.get("name", "").strip()
    account_name = request.POST.get("account_name", "").strip()
    account_number = request.POST.get("account_number", "").strip()
    is_default = request.POST.get("is_default") in ("on", "true", "1")

    if not name or not account_name or not account_number:
        messages.error(request, "Name, account title, and account number are required.")
        return redirect("/settings")

    if is_default:
        PaymentAccount.objects.filter(category=category).update(is_default=False)

    account = PaymentAccount.objects.create(
        category=category,
        name=name,
        account_name=account_name,
        account_number=account_number,
        is_active=True,
        is_default=is_default,
    )
    messages.success(request, f"Added {account.get_category_display()}: {account.name}")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse({"success": True, "account": account.to_dict()})
    return redirect("/settings")


@csrf_exempt
@login_required_pos
def payment_account_edit(request, account_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        account = PaymentAccount.objects.get(id=account_id)
    except PaymentAccount.DoesNotExist:
        messages.error(request, "Payment account not found.")
        return redirect("/settings")

    category = request.POST.get("category", account.category).strip().lower()
    if category in ("bank", "wallet"):
        account.category = category

    name = request.POST.get("name", account.name).strip()
    account_name = request.POST.get("account_name", account.account_name).strip()
    account_number = request.POST.get("account_number", account.account_number).strip()
    is_active = request.POST.get("is_active") in ("on", "true", "1")
    is_default = request.POST.get("is_default") in ("on", "true", "1")

    if not name or not account_name or not account_number:
        messages.error(request, "Name, account title, and account number cannot be empty.")
        return redirect("/settings")

    if is_default and not account.is_default:
        PaymentAccount.objects.filter(category=account.category).update(is_default=False)

    account.name = name
    account.account_name = account_name
    account.account_number = account_number
    account.is_active = is_active
    account.is_default = is_default
    account.save()

    messages.success(request, f"Updated {account.name} successfully")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse({"success": True, "account": account.to_dict()})
    return redirect("/settings")


@csrf_exempt
@login_required_pos
def payment_account_toggle(request, account_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        account = PaymentAccount.objects.get(id=account_id)
    except PaymentAccount.DoesNotExist:
        return JsonResponse({"error": "Account not found"}, status=404)

    account.is_active = not account.is_active
    account.save(update_fields=["is_active", "updated_at"])
    state = "activated" if account.is_active else "deactivated"
    messages.success(request, f"{account.name} {state}")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse({"success": True, "is_active": account.is_active})
    return redirect("/settings")


@csrf_exempt
@login_required_pos
def payment_account_delete(request, account_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        account = PaymentAccount.objects.get(id=account_id)
    except PaymentAccount.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect("/settings")

    name = account.name
    account.delete()
    messages.success(request, f"Deleted account: {name}")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse({"success": True})
    return redirect("/settings")



