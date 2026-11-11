import csv
import io
import datetime
from functools import wraps

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from apps.core.models import StoreSettings


def get_store_settings():
    return StoreSettings.get_settings()


def render_pos(request, template_name, context=None):
    if context is None:
        context = {}

    settings_obj = get_store_settings()

    def get_flashed_messages(with_categories=False):
        storage = messages.get_messages(request)
        msgs = list(storage)
        if with_categories:
            cat_map = {"error": "error", "success": "success", "warning": "error", "info": "info"}
            return [(cat_map.get(m.tags, "info"), str(m.message)) for m in msgs]
        return [str(m.message) for m in msgs]

    full_context = {
        "request": request,
        "session": request.session,
        "user": request.user,
        "settings": settings_obj,
        "get_flashed_messages": get_flashed_messages,
        "active_view": context.get("active_view", ""),
    }
    full_context.update(context)

    return render(request, template_name, full_context, using="jinja2")


def login_required_pos(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_authenticated or "user_id" in request.session):
            return redirect("/login")
        return view_func(request, *args, **kwargs)
    return _wrapped


def admin_required_pos(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not (request.user.is_authenticated or "user_id" in request.session):
            return redirect("/login")
        user_role = getattr(request.user, "role", None) or request.session.get("user_role")
        if user_role != "admin" and not getattr(request.user, "is_superuser", False):
            messages.error(request, "Admin access required")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped


def csv_response(filename, columns, rows):
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow([label for _, label in columns])
    for row in rows:
        if isinstance(row, dict):
            writer.writerow([str(row.get(key, "") or "") for key, _ in columns])
        else:
            writer.writerow([str(getattr(row, key, "") or "") for key, _ in columns])
    output = si.getvalue()
    response = HttpResponse(output, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def parse_float(val, default=0.0):
    try:
        return float(val) if val is not None and str(val).strip() != "" else default
    except (ValueError, TypeError):
        return default


def parse_int(val, default=0):
    try:
        return int(val) if val is not None and str(val).strip() != "" else default
    except (ValueError, TypeError):
        return default


def get_date_range(request):
    now = timezone.now()
    default_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    default_to = now.replace(hour=23, minute=59, second=59, microsecond=0)

    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")

    if date_from_raw:
        try:
            if len(date_from_raw) == 10:
                date_from_raw += "T00:00:00"
            dt = datetime.datetime.fromisoformat(date_from_raw)
            date_from = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except (ValueError, TypeError):
            date_from = default_from
    else:
        date_from = default_from

    if date_to_raw:
        try:
            if len(date_to_raw) == 10:
                date_to_raw += "T23:59:59"
            dt = datetime.datetime.fromisoformat(date_to_raw)
            date_to = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except (ValueError, TypeError):
            date_to = default_to
    else:
        date_to = default_to

    return date_from, date_to
