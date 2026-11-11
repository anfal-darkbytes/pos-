import random
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import PasswordResetOTP, User
from apps.core.models import StoreSettings
from apps.core.utils import admin_required_pos, render_pos


def send_otp_email(to_email, otp):
    settings = StoreSettings.get_settings()
    host = settings.smtp_host
    port = settings.smtp_port
    user = settings.smtp_user
    pwd = settings.smtp_pass
    from_email = settings.smtp_from_email or user
    if not host or not user or not pwd:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Pulse POS — Your OTP is {otp}"
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(
            f"Hello,\n\n"
            f"Your OTP for password reset is: {otp}\n\n"
            f"This code expires in 10 minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"— Pulse POS Team"
        )
        port_int = int(port) if port else 587
        with smtplib.SMTP(host, port_int, timeout=10) as server:
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)
        return True
    except Exception:
        return False


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
    # Prevent active session users from creating accounts without signing out
    if request.user.is_authenticated or "user_id" in request.session:
        messages.info(request, "Please log out of your current session before registering a new account.")
        return redirect("/")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if not name or not email or not password:
            messages.error(request, "All fields are required")
            return redirect("/register")
        if password != confirm:
            messages.error(request, "Passwords do not match")
            return redirect("/register")
        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return redirect("/register")
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already registered")
            return redirect("/register")

        username = email.split("@")[0]
        # Ensure unique username
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            name=name,
            email=email,
            role="cashier",
            is_active=True,
        )
        user.set_password(password)
        user.save()

        messages.success(request, "Registration successful! You can now log in.")
        return redirect("/login")

    if request.user.is_authenticated or "user_id" in request.session:
        return redirect("/")
    return render_pos(request, "register.html")


@csrf_exempt
def forgot_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, "No account found with that email")
            return redirect("/forgot")

        otp = f"{random.randint(100000, 999999)}"
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        PasswordResetOTP.objects.create(email=email, otp=otp, otp_expires_at=expires)

        sent = send_otp_email(email, otp)
        if not sent:
            messages.error(request, "Could not send email. SMTP not configured. Contact your admin.")
            return redirect("/forgot")

        request.session["reset_email"] = email
        messages.success(request, f"OTP sent to {email}")
        return redirect("/reset-password")

    return render_pos(request, "forgot.html")


@csrf_exempt
def reset_password_view(request):
    email = request.session.get("reset_email")
    if not email:
        return redirect("/forgot")

    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if password != confirm:
            messages.error(request, "Passwords do not match")
            return redirect("/reset-password")
        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return redirect("/reset-password")

        now = datetime.now(timezone.utc)
        record = PasswordResetOTP.objects.filter(
            email=email, otp=otp, used=False, otp_expires_at__gt=now
        ).order_by("-created_at").first()

        if not record:
            messages.error(request, "Invalid or expired OTP")
            return redirect("/reset-password")

        user = User.objects.filter(email__iexact=email).first()
        if user:
            user.set_password(password)
            user.save()
            record.used = True
            record.save()
            request.session.pop("reset_email", None)
            messages.success(request, "Password reset successful! You can now log in.")
            return redirect("/login")
        else:
            messages.error(request, "User account not found")
            return redirect("/login")

    return render_pos(request, "reset_password.html")


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

