from datetime import datetime, timedelta, timezone

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import User
from apps.core.models import StoreSettings
from apps.core.utils import admin_required_pos, login_required_pos, render_pos


@csrf_exempt
def login_view(request):
    # If the user already has an active 30-day session, prevent redundant login
    if request.user.is_authenticated or "user_id" in request.session:
        user = getattr(request, "user", None)
        if not (user and getattr(user, "is_authenticated", False)):
            uid = request.session.get("user_id")
            user = User.objects.filter(id=uid, is_active=True).first() if uid else None

        if user and user.is_active:
            messages.info(request, f"You are already signed in as {user.name or user.username} with an active 30-day session.")
            return redirect("/")
        else:
            # Stale session, clean up to permit fresh sign in
            request.session.flush()

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            # Also allow username login
            user = User.objects.filter(username__iexact=email).first()

        if user and user.is_active and (user.check_password(password) or check_password(password, user.password)):
            login(request, user)
            # Enforce 30-day session expiry (30 days * 24 hours * 60 minutes * 60 seconds)
            THIRTY_DAYS = 60 * 60 * 24 * 30
            request.session.set_expiry(THIRTY_DAYS)
            request.session["user_id"] = str(user.id)
            request.session["user_name"] = user.name or user.username
            request.session["user_role"] = user.role
            request.session["login_time"] = datetime.now(timezone.utc).isoformat()
            request.session.modified = True
            messages.success(request, f"Welcome back, {user.name or user.username}! Your session is active for 30 days.")
            return redirect("/")
        else:
            messages.error(request, "Invalid email or password")
            return redirect("/login")

    return render_pos(request, "login.html")


def logout_view(request):
    logout(request)
    request.session.flush()
    messages.info(request, "You have been logged out successfully.")
    return redirect("/login")


@csrf_exempt
def register_view(request):
    """
    Public self-registration is disabled.
    Staff accounts are provisioned exclusively by system administrators in the Users panel.
    """
    if request.user.is_authenticated and (getattr(request.user, "role", None) == "admin" or getattr(request.user, "is_superuser", False)):
        messages.info(request, "Staff registration is centralized in the Users management panel.")
        return redirect("/users")
    messages.info(request, "Self-registration is disabled. Please contact your system administrator to obtain access credentials.")
    return redirect("/login")


@csrf_exempt
def forgot_view(request):
    """
    Self-service password recovery is disabled.
    Credentials and password resets are managed exclusively by store administrators in the Users panel.
    """
    messages.info(request, "Self-service password recovery is disabled. Please contact your store administrator to reset your credentials.")
    return redirect("/login")


@csrf_exempt
def reset_password_view(request):
    """
    Self-service password reset is disabled.
    """
    messages.info(request, "Self-service password recovery is disabled. Please contact your store administrator to reset your credentials.")
    return redirect("/login")


@csrf_exempt
@login_required_pos
def profile_view(request):
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    if not user:
        uid = request.session.get("user_id")
        user = User.objects.filter(id=uid).first() if uid else None

    if not user:
        messages.error(request, "Session not found. Please log in.")
        return redirect("/login")

    if request.method == "POST":
        action = request.POST.get("action", "update_profile")

        if action == "update_profile":
            name = request.POST.get("name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("phone", "").strip()

            if not name or not email:
                messages.error(request, "Name and Email are required.")
                return redirect("/profile")

            if User.objects.filter(email__iexact=email).exclude(id=user.id).exists():
                messages.error(request, "This email address is already in use by another account.")
                return redirect("/profile")

            user.name = name
            user.email = email
            user.phone = phone
            user.save()

            request.session["user_name"] = user.name or user.username
            request.session.modified = True
            messages.success(request, "Profile updated successfully.")
            return redirect("/profile")

        elif action == "change_password":
            current_password = request.POST.get("current_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            if not current_password or not new_password or not confirm_password:
                messages.error(request, "All password fields are required.")
                return redirect("/profile")

            if not (user.check_password(current_password) or check_password(current_password, user.password)):
                messages.error(request, "Current password is incorrect.")
                return redirect("/profile")

            if new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
                return redirect("/profile")

            if len(new_password) < 6:
                messages.error(request, "New password must be at least 6 characters.")
                return redirect("/profile")

            user.set_password(new_password)
            user.save()
            login(request, user)
            messages.success(request, "Password updated successfully.")
            return redirect("/profile")

    login_time = request.session.get("login_time")
    settings = StoreSettings.get_settings()

    return render_pos(
        request,
        "profile.html",
        {
            "active_view": "profile",
            "profile_user": user,
            "login_time": login_time,
            "settings": settings,
        },
    )


@admin_required_pos
def users_view(request):
    users = User.objects.all().order_by("-date_joined")
    return render_pos(request, "users.html", {"active_view": "users", "users": users})


@csrf_exempt
@admin_required_pos
def users_new(request):
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip().lower()
    password = request.POST.get("password", "")
    role = request.POST.get("role", "cashier")

    if not name or not email or not password:
        messages.error(request, "All fields are required")
        return redirect("/users")

    if User.objects.filter(email__iexact=email).exists():
        messages.error(request, "Email already in use")
        return redirect("/users")

    username = email.split("@")[0]
    base_username = username
    c = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{c}"
        c += 1

    user = User.objects.create(
        username=username,
        name=name,
        email=email,
        role=role,
        is_active=True,
    )
    user.set_password(password)
    user.save()

    messages.success(request, f"User {name} created")
    return redirect("/users")


@csrf_exempt
@admin_required_pos
def users_edit(request, user_id):
    user = User.objects.filter(id=user_id).first()
    if not user:
        messages.error(request, "User not found")
        return redirect("/users")

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip().lower()
    role = request.POST.get("role", "cashier")
    password = request.POST.get("password", "")

    if not name or not email:
        messages.error(request, "Name and email are required")
        return redirect("/users")

    if User.objects.filter(email__iexact=email).exclude(id=user_id).exists():
        messages.error(request, "Email already in use")
        return redirect("/users")

    user.name = name
    user.email = email
    user.role = role
    if password:
        user.set_password(password)
    user.save()

    messages.success(request, "User updated")
    return redirect("/users")


@csrf_exempt
@admin_required_pos
def users_delete(request, user_id):
    current_id = str(request.user.id) if request.user.is_authenticated else request.session.get("user_id")
    if str(user_id) == str(current_id):
        messages.error(request, "You cannot delete yourself")
        return redirect("/users")

    User.objects.filter(id=user_id).delete()
    messages.success(request, "User deleted")
    return redirect("/users")


@csrf_exempt
@admin_required_pos
def users_toggle(request, user_id):
    current_id = str(request.user.id) if request.user.is_authenticated else request.session.get("user_id")
    if str(user_id) == str(current_id):
        messages.error(request, "You cannot deactivate yourself")
        return redirect("/users")

    user = User.objects.filter(id=user_id).first()
    if user:
        user.is_active = not user.is_active
        user.save()
        messages.success(request, f"User {'activated' if user.is_active else 'deactivated'}")
    return redirect("/users")

