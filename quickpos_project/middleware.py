from django.utils.deprecation import MiddlewareMixin
from apps.accounts.models import User


class PulsePOSSessionAuthMiddleware(MiddlewareMixin):
    """
    Maintains persistent 30-day session integrity, synchronizes request.user
    with request.session, and ensures sliding expiration is preserved across requests.
    """
    def process_request(self, request):
        if request.user.is_authenticated:
            request.session["user_id"] = str(request.user.id)
            request.session["user_name"] = request.user.name or request.user.username
            request.session["user_role"] = getattr(request.user, "role", "cashier")
        elif "user_id" in request.session:
            try:
                user_id = request.session["user_id"]
                user = User.objects.filter(id=user_id, is_active=True).first()
                if user:
                    request.user = user
                    request.session["user_name"] = user.name or user.username
                    request.session["user_role"] = getattr(user, "role", "cashier")
                else:
                    request.session.flush()
            except Exception:
                request.session.flush()


# Backwards compatibility alias
QuickPOSSessionAuthMiddleware = PulsePOSSessionAuthMiddleware
