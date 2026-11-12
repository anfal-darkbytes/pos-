import json
from datetime import datetime, timezone
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet
from django.forms.models import model_to_dict
from django.templatetags.static import static
from django.urls import reverse, NoReverseMatch
from jinja2 import Environment, pass_context
import markupsafe


class POSJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Model):
            d = model_to_dict(o)
            # Add custom computed attributes
            for attr in [
                "id", "margin", "stock_value", "is_low", "tier", "tier_color",
                "category_color", "category_name", "category_id_str"
            ]:
                if hasattr(o, attr):
                    val = getattr(o, attr)
                    if isinstance(val, Decimal):
                        val = float(val)
                    elif hasattr(val, "isoformat"):
                        val = val.isoformat()
                    d[attr] = str(val) if attr == "id" else val
            return d
        if isinstance(o, QuerySet):
            return list(o)
        if isinstance(o, Decimal):
            return float(o)
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return super().default(o)


@pass_context
def fmt_money(context, amount=0, symbol=None):
    # Support direct invocation without Jinja context: fmt_money(amount, symbol)
    if not isinstance(context, dict) and not hasattr(context, "get"):
        val_arg = context
        sym_arg = amount if isinstance(amount, str) else "$"
        try:
            val = float(val_arg or 0)
        except (ValueError, TypeError):
            val = 0.0
        return f"{sym_arg}{val:,.2f}"

    if amount is None:
        amount = 0
    try:
        val = float(amount)
    except (ValueError, TypeError):
        val = 0.0

    if symbol is None:
        settings = context.get("settings") if hasattr(context, "get") else None
        if isinstance(settings, dict):
            symbol = settings.get("currency_symbol") or "$"
        elif hasattr(settings, "currency_symbol"):
            symbol = getattr(settings, "currency_symbol", "$") or "$"
        else:
            try:
                from apps.core.models import StoreSettings
                symbol = StoreSettings.get_settings().currency_symbol or "$"
            except Exception:
                symbol = "$"
    return f"{symbol}{val:,.2f}"


def _parse_dt(dt_val):
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(dt_val, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    return None


def fmt_date(dt_val):
    dt = _parse_dt(dt_val)
    if not dt:
        return str(dt_val or "")
    return dt.strftime("%b %d, %Y %I:%M %p")


def fmt_date_short(dt_val):
    dt = _parse_dt(dt_val)
    if not dt:
        return str(dt_val or "")
    return dt.strftime("%b %d, %Y")


def time_ago(dt_val):
    dt = _parse_dt(dt_val)
    if not dt:
        return str(dt_val or "")
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    secs = diff.total_seconds()
    if secs < 60:
        return "just now"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m ago"
    hours = int(mins // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%b %d, %Y")


def customer_tier(points):
    try:
        pts = int(points or 0)
    except (ValueError, TypeError):
        pts = 0
    if pts >= 400:
        return "Platinum", "bg-purple-500"
    if pts >= 200:
        return "Gold", "bg-amber-500"
    if pts >= 100:
        return "Silver", "bg-slate-400"
    return "Bronze", "bg-orange-700"


def tojson_filter(val):
    if hasattr(val, "to_dict"):
        val = val.to_dict()
    return markupsafe.Markup(json.dumps(val, cls=POSJSONEncoder))


def url_for(endpoint, **values):
    if endpoint == "static":
        filename = values.get("filename", "")
        return static(filename)
    try:
        return reverse(endpoint, kwargs=values)
    except NoReverseMatch:
        pass
    try:
        return reverse(endpoint)
    except NoReverseMatch:
        # Fallback to direct path
        endpoint_clean = endpoint.replace("_", "-")
        return f"/{endpoint_clean}"


def environment(**options):
    env = Environment(**options)

    # Custom filters
    env.filters["money"] = fmt_money
    env.filters["date"] = fmt_date
    env.filters["date_short"] = fmt_date_short
    env.filters["time_ago"] = time_ago
    env.filters["tier"] = lambda p: customer_tier(p)[0]
    env.filters["tier_color"] = lambda p: customer_tier(p)[1]
    env.filters["tojson"] = tojson_filter

    # Global functions
    env.globals["url_for"] = url_for
    env.globals["static"] = static

    return env

