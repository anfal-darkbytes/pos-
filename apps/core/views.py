import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import StoreSettings, PaymentAccount
from apps.core.utils import admin_required_pos, login_required_pos, parse_float, render_pos

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

BACKUP_DIR = os.path.join(django_settings.BASE_DIR, "backups")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _fmt_size(num):
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


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



def _backup_list():
    _ensure_backup_dir()
    files = []
    for f in sorted(Path(BACKUP_DIR).glob("quickpos_*.db"), reverse=True):
        size = os.path.getsize(f)
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        files.append({"name": f.name, "size": size, "size_fmt": _fmt_size(size), "mtime": mtime})
    return files


def _gdrive_creds():
    if not GOOGLE_LIBS_AVAILABLE:
        return None
    token_path = os.path.join(BACKUP_DIR, "token.json")
    if not os.path.exists(token_path):
        return None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        return creds if creds and creds.valid else None
    except Exception:
        return None


def _gdrive_list():
    creds = _gdrive_creds()
    if not creds or not GOOGLE_LIBS_AVAILABLE:
        return []
    try:
        service = build("drive", "v3", credentials=creds)
        res = service.files().list(
            q="name contains 'quickpos_' and trashed = false",
            fields="files(id, name, size, createdTime, webViewLink)",
            orderBy="createdTime desc",
            pageSize=20
        ).execute()
        files = res.get("files", [])
        for f in files:
            size = int(f.get("size", 0))
            f["size_fmt"] = _fmt_size(size)
            f["created_fmt"] = f.get("createdTime", "")[:19].replace("T", " ")
        return files
    except Exception:
        return []


def _get_db_path():
    db_conf = django_settings.DATABASES.get("default", {})
    return str(db_conf.get("NAME", os.path.join(django_settings.BASE_DIR, "quickpos.sqlite3")))


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
        settings.currency = request.POST.get("currency", settings.currency)
        settings.currency_symbol = request.POST.get("currency_symbol", settings.currency_symbol)
        settings.receipt_footer = request.POST.get("receipt_footer", settings.receipt_footer)
        settings.low_stock_alert_enabled = request.POST.get("low_stock_alert_enabled") in ("on", "true", "1")

        settings.smtp_host = request.POST.get("smtp_host", "").strip() or None
        settings.smtp_port = request.POST.get("smtp_port", "").strip() or None
        settings.smtp_user = request.POST.get("smtp_user", "").strip() or None
        settings.smtp_pass = request.POST.get("smtp_pass", "").strip() or None
        settings.smtp_from_email = request.POST.get("smtp_from_email", "").strip() or None

        settings.gdrive_client_id = request.POST.get("gdrive_client_id", "").strip() or None
        settings.gdrive_client_secret = request.POST.get("gdrive_client_secret", "").strip() or None
        settings.save()

        messages.success(request, "Settings saved successfully")
        return redirect("/settings")

    PaymentAccount.seed_default_accounts_if_empty()
    payment_accounts = PaymentAccount.objects.all().order_by("category", "name")

    currencies = [
        ("USD", "$", "US Dollar"), ("EUR", "€", "Euro"), ("GBP", "£", "British Pound"),
        ("PKR", "Rs", "Pakistani Rupee"), ("INR", "₹", "Indian Rupee"), ("JPY", "¥", "Japanese Yen"),
        ("CNY", "¥", "Chinese Yuan"), ("AUD", "A$", "Australian Dollar"),
        ("CAD", "C$", "Canadian Dollar"),
    ]
    return render_pos(
        request,
        "settings.html",
        {
            "active_view": "settings",
            "settings": settings,
            "currencies": currencies,
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


@admin_required_pos
def backup_view(request):
    settings = StoreSettings.get_settings()
    db_path = _get_db_path()
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat() if os.path.exists(db_path) else ""
    snapshots = _backup_list()
    creds = _gdrive_creds()
    gdrive_connected = creds is not None and creds.valid
    gdrive_files = _gdrive_list() if gdrive_connected else []

    return render_pos(
        request,
        "backup.html",
        {
            "active_view": "backup",
            "settings": settings,
            "db_size": db_size,
            "db_size_fmt": _fmt_size(db_size),
            "db_mtime": db_mtime,
            "snapshots": snapshots,
            "gdrive_connected": gdrive_connected,
            "gdrive_files": gdrive_files,
        },
    )


@csrf_exempt
@admin_required_pos
def backup_create(request):
    _ensure_backup_dir()
    db_path = _get_db_path()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name = f"quickpos_{ts}.db"
    dest = os.path.join(BACKUP_DIR, name)
    try:
        if os.path.exists(db_path):
            shutil.copy2(db_path, dest)
            messages.success(request, f"Backup created: {name}")
        else:
            messages.error(request, "Database file not found to backup")
    except Exception as e:
        messages.error(request, f"Backup failed: {e}")
    return redirect("/backup")


@admin_required_pos
def backup_download(request):
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        messages.error(request, "Database file not found")
        return redirect("/backup")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return FileResponse(open(db_path, "rb"), as_attachment=True, filename=f"quickpos_{ts}.db")


@admin_required_pos
def backup_download_snapshot(request, filename):
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(path) or not safe.startswith("quickpos_") or not safe.endswith(".db"):
        messages.error(request, "Invalid backup file")
        return redirect("/backup")
    return FileResponse(open(path, "rb"), as_attachment=True, filename=safe)


@csrf_exempt
@admin_required_pos
def backup_delete(request, filename):
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if os.path.exists(path) and safe.startswith("quickpos_") and safe.endswith(".db"):
        os.remove(path)
        messages.success(request, f"Deleted {safe}")
    else:
        messages.error(request, "Invalid backup file")
    return redirect("/backup")


@csrf_exempt
@admin_required_pos
def backup_auth_google(request):
    settings = StoreSettings.get_settings()
    cid = settings.gdrive_client_id
    csec = settings.gdrive_client_secret
    if not cid or not csec or not GOOGLE_LIBS_AVAILABLE:
        messages.error(request, "Google Drive Client ID and Secret must be configured in Settings")
        return redirect("/backup")

    _ensure_backup_dir()

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        if not code:
            messages.error(request, "Authorization code is required")
            return redirect("/backup/auth/google")
        try:
            cred_path = os.path.join(BACKUP_DIR, "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            flow.fetch_token(code=code)
            creds = flow.credentials
            token_path = os.path.join(BACKUP_DIR, "token.json")
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            messages.success(request, "Google Drive connected successfully!")
            return redirect("/backup")
        except Exception as e:
            messages.error(request, f"Token exchange failed: {e}")
            return redirect("/backup/auth/google")

    cred_data = {
        "installed": {
            "client_id": cid,
            "client_secret": csec,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    cred_path = os.path.join(BACKUP_DIR, "credentials.json")
    with open(cred_path, "w") as f:
        json.dump(cred_data, f)
    flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url = flow.authorization_url(access_type="offline", include_granted_scopes="true")[0]
    return render_pos(request, "backup_auth.html", {"auth_url": auth_url})


@csrf_exempt
@admin_required_pos
def backup_upload(request, filename):
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(path) or not safe.startswith("quickpos_") or not safe.endswith(".db"):
        messages.error(request, "Invalid backup file")
        return redirect("/backup")

    creds = _gdrive_creds()
    if not creds or not creds.valid or not GOOGLE_LIBS_AVAILABLE:
        messages.error(request, "Google Drive not connected. Click 'Connect to Google Drive' first.")
        return redirect("/backup")

    try:
        service = build("drive", "v3", credentials=creds)
        file_metadata = {"name": safe, "parents": []}
        media = MediaFileUpload(path, mimetype="application/octet-stream", resumable=True)
        uploaded = service.files().create(body=file_metadata, media_body=media, fields="id,name,size,createdTime").execute()
        file_name = uploaded.get("name")
        messages.success(request, f"Uploaded {file_name} to Google Drive")
    except Exception as e:
        messages.error(request, f"Upload failed: {e}")
    return redirect("/backup")

